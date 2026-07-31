from __future__ import annotations

"""Background session recorder consuming directly from StreamHub.

The GUI-facing :class:`SessionRecorder` is a small QObject facade.  All frame
consumption, CSV appends, metadata generation, snapshots, and autosaves happen
inside a dedicated Python thread.  This prevents disk latency from delaying Qt
painting or serial-device polling.
"""

import csv
import json
import queue
import re
import shutil
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml
from PyQt5 import QtCore

from ..data.models import LogEvent, SensorDefinition, SensorFrame
from ..data.stream_hub import OverflowPolicy, StreamHub, StreamSubscription


@dataclass
class _RecorderCommand:
    """Private request passed from the GUI facade to the recorder thread."""

    name: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)
    completed: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: BaseException | None = None


class _RecorderState:
    """Pure file/state implementation used only by the recorder thread."""

    def __init__(
        self,
        *,
        sensor_definitions: dict[str, SensorDefinition],
        base_directory: str | Path,
        autosave_interval_s: int,
    ) -> None:
        self.sensor_definitions = dict(sensor_definitions)
        self.base_directory = Path(base_directory)
        self.autosave_interval_s = max(5, int(autosave_interval_s))

        self.app_started_utc = datetime.now(timezone.utc)
        self.app_started_monotonic = time.monotonic()
        self.session_directory: Path | None = None
        self.sensor_logging_active = False
        self.selected_sensor_ids: set[str] = set()
        self.sensor_logging_started_utc: datetime | None = None
        self.sensor_logging_started_monotonic: float | None = None
        self.sensor_logging_stopped_monotonic: float | None = None
        self.sensor_logging_stopped_utc: datetime | None = None
        self._frame_elapsed_origin: float | None = None

        self._pending_logs: list[LogEvent] = []
        self._pending_sensor_rows: dict[
            str,
            list[tuple[str, float, float, Any, Any, int, str]],
        ] = defaultdict(list)
        self._sample_counts: dict[str, int] = defaultdict(int)
        self._first_sensor_elapsed: dict[str, float] = {}
        self._last_sensor_elapsed: dict[str, float] = {}
        self._created_sensor_files: set[str] = set()
        self._finalized = False

    # ------------------------------------------------------------------
    # Ingestion from hub subscriptions
    # ------------------------------------------------------------------
    def ingest_log(self, event: LogEvent) -> None:
        self._pending_logs.append(event)

    def ingest_frame(self, frame: SensorFrame) -> None:
        if not self.sensor_logging_active:
            return
        if self._frame_elapsed_origin is None:
            self._frame_elapsed_origin = frame.elapsed_s
        recording_elapsed = max(0.0, frame.elapsed_s - self._frame_elapsed_origin)

        # Each selected channel from this frame receives exactly the same host
        # timestamp and elapsed time, preserving synchronized firmware frames.
        for sensor_id in self.selected_sensor_ids:
            if sensor_id not in frame.values:
                continue
            value = float(frame.values[sensor_id])
            self._pending_sensor_rows[sensor_id].append(
                (
                    frame.timestamp_utc,
                    recording_elapsed,
                    value,
                    frame.sequence,
                    frame.device_timestamp,
                    frame.host_received_monotonic_ns,
                    frame.source_id,
                )
            )
            self._sample_counts[sensor_id] += 1
            self._first_sensor_elapsed.setdefault(sensor_id, recording_elapsed)
            self._last_sensor_elapsed[sensor_id] = recording_elapsed

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    def set_base_directory(self, path: str | Path) -> None:
        if self.session_directory is not None:
            raise RuntimeError("Cannot change the session root after a session folder has been created")
        self.base_directory = Path(path)

    def set_autosave_interval(self, seconds: int) -> None:
        self.autosave_interval_s = max(5, int(seconds))

    def start_sensor_logging(self, sensor_ids: Iterable[str]) -> Path:
        if self._finalized:
            raise RuntimeError("This application session has already been finalized")
        selected = {str(sensor_id) for sensor_id in sensor_ids}
        unknown = selected.difference(self.sensor_definitions)
        if unknown:
            raise KeyError(f"Unknown sensor IDs: {sorted(unknown)}")
        selected = {sensor_id for sensor_id in selected if self.sensor_definitions[sensor_id].enabled}
        if not selected:
            raise ValueError("Select at least one enabled sensor")
        if self.sensor_logging_active:
            raise RuntimeError("Sensor logging is already active")

        self.ensure_session_directory()
        self.selected_sensor_ids = selected
        self.sensor_logging_active = True
        self.sensor_logging_started_utc = datetime.now(timezone.utc)
        self.sensor_logging_started_monotonic = time.monotonic()
        self.sensor_logging_stopped_monotonic = None
        self.sensor_logging_stopped_utc = None
        self._frame_elapsed_origin = None
        return self.session_directory  # type: ignore[return-value]

    def stop_sensor_logging(self) -> Path:
        if self.sensor_logging_active:
            self.sensor_logging_active = False
            self.sensor_logging_stopped_monotonic = time.monotonic()
            self.sensor_logging_stopped_utc = datetime.now(timezone.utc)
        return self.save_now()

    def save_now(self) -> Path:
        directory = self.ensure_session_directory()
        self._flush_logs()
        self._flush_sensor_rows()
        self._write_metadata_files(final=False)
        self._write_manifest(final=False)
        return directory

    def save_snapshot(self) -> Path:
        directory = self.save_now()
        snapshot_root = directory / "snapshots"
        snapshot_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        snapshot_dir = _unique_directory(snapshot_root / f"snapshot_{stamp}")
        snapshot_dir.mkdir(parents=True, exist_ok=False)
        for item in directory.iterdir():
            if item.name == "snapshots":
                continue
            destination = snapshot_dir / item.name
            if item.is_file():
                shutil.copy2(item, destination)
            elif item.is_dir():
                shutil.copytree(item, destination)
        return snapshot_dir

    def export_logs(self, destination: str | Path) -> Path:
        self.save_now()
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = self.ensure_session_directory() / "system_log.csv"
        shutil.copy2(source, destination)
        return destination

    def finalize(self) -> Path:
        if self._finalized:
            return self.ensure_session_directory()
        if self.sensor_logging_active:
            self.sensor_logging_active = False
            self.sensor_logging_stopped_monotonic = time.monotonic()
            self.sensor_logging_stopped_utc = datetime.now(timezone.utc)
        directory = self.ensure_session_directory()
        self._flush_logs()
        self._flush_sensor_rows()
        self._write_metadata_files(final=True)
        self._write_manifest(final=True)
        self._finalized = True
        return directory

    def ensure_session_directory(self) -> Path:
        if self.session_directory is not None:
            return self.session_directory
        self.base_directory.mkdir(parents=True, exist_ok=True)
        stamp = self.app_started_utc.astimezone().strftime("%Y-%m-%d_%H-%M-%S")
        directory = _unique_directory(self.base_directory / stamp)
        directory.mkdir(parents=True, exist_ok=False)
        self.session_directory = directory
        return directory

    # ------------------------------------------------------------------
    # Incremental file writing
    # ------------------------------------------------------------------
    def _flush_logs(self) -> None:
        if not self._pending_logs:
            return
        path = self.ensure_session_directory() / "system_log.csv"
        write_header = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if write_header:
                writer.writerow(
                    ["timestamp_utc", "elapsed_app_s", "level", "source", "message", "details_json"]
                )
            for event in self._pending_logs:
                writer.writerow(
                    [
                        event.timestamp_utc,
                        f"{event.elapsed_s:.6f}",
                        event.level,
                        event.source,
                        event.message,
                        json.dumps(event.details, sort_keys=True),
                    ]
                )
        self._pending_logs.clear()

    def _flush_sensor_rows(self) -> None:
        for sensor_id, rows in list(self._pending_sensor_rows.items()):
            if not rows:
                continue
            self._ensure_sensor_file(sensor_id)
            with self._sensor_csv_path(sensor_id).open("a", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                for (
                    timestamp_utc,
                    elapsed_s,
                    value,
                    sequence,
                    device_timestamp,
                    host_received_monotonic_ns,
                    source_id,
                ) in rows:
                    writer.writerow(
                        [
                            timestamp_utc,
                            f"{elapsed_s:.9f}",
                            f"{value:.12g}",
                            "" if sequence is None else sequence,
                            "" if device_timestamp is None else device_timestamp,
                            host_received_monotonic_ns,
                            source_id,
                        ]
                    )
            rows.clear()

    def _ensure_sensor_file(self, sensor_id: str) -> None:
        if sensor_id in self._created_sensor_files:
            return
        definition = self.sensor_definitions[sensor_id]
        path = self._sensor_csv_path(sensor_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with path.open("w", newline="", encoding="utf-8") as handle:
                handle.write(f"# sensor_id: {definition.sensor_id}\n")
                handle.write(f"# sensor_label: {definition.label}\n")
                handle.write(f"# source_device: {definition.source_device}\n")
                handle.write(f"# source_channel: {definition.source_channel}\n")
                handle.write(f"# unit: {definition.unit}\n")
                handle.write(
                    "# configured_sampling_frequency_hz: "
                    f"{definition.expected_sampling_hz if definition.expected_sampling_hz is not None else ''}\n"
                )
                handle.write(f"# application_session_started_utc: {self.app_started_utc.isoformat()}\n")
                writer = csv.writer(handle)
                writer.writerow(
                    [
                        "timestamp_utc",
                        "elapsed_s",
                        "value",
                        "sequence",
                        "device_timestamp",
                        "host_received_monotonic_ns",
                        "source_device",
                    ]
                )
        self._created_sensor_files.add(sensor_id)

    def _sensor_csv_path(self, sensor_id: str) -> Path:
        definition = self.sensor_definitions[sensor_id]
        filename = f"{_safe_name(definition.sensor_id)}__{_safe_name(definition.label)}.csv"
        return self.ensure_session_directory() / filename

    def _sensor_metadata_path(self, sensor_id: str) -> Path:
        definition = self.sensor_definitions[sensor_id]
        filename = f"{_safe_name(definition.sensor_id)}__{_safe_name(definition.label)}_metadata.yaml"
        return self.ensure_session_directory() / filename

    def _write_metadata_files(self, *, final: bool) -> None:
        for sensor_id in sorted(self.selected_sensor_ids):
            definition = self.sensor_definitions[sensor_id]
            count = self._sample_counts.get(sensor_id, 0)
            first = self._first_sensor_elapsed.get(sensor_id)
            last = self._last_sensor_elapsed.get(sensor_id)
            measured_duration = (last - first) if first is not None and last is not None else 0.0
            actual_hz = ((count - 1) / measured_duration) if count > 1 and measured_duration > 0 else None
            metadata = {
                "sensor_id": definition.sensor_id,
                "sensor_label": definition.label,
                "source_device": definition.source_device,
                "source_channel": definition.source_channel,
                "unit": definition.unit,
                "configured_sampling_frequency_hz": definition.expected_sampling_hz,
                "estimated_sampling_frequency_hz": actual_hz,
                "sample_count": count,
                "total_elapsed_time_s": self.recording_elapsed_s(),
                "sensor_logging_started_utc": (
                    self.sensor_logging_started_utc.isoformat() if self.sensor_logging_started_utc else None
                ),
                "sensor_logging_stopped_utc": (
                    self.sensor_logging_stopped_utc.isoformat() if self.sensor_logging_stopped_utc else None
                ),
                "finalized": final,
                "description": definition.description,
                "metadata": dict(definition.metadata),
            }
            self._sensor_metadata_path(sensor_id).write_text(
                yaml.safe_dump(metadata, sort_keys=False),
                encoding="utf-8",
            )

    def _write_manifest(self, *, final: bool) -> None:
        directory = self.ensure_session_directory()
        manifest = {
            "schema_version": 2,
            "application_session_started_utc": self.app_started_utc.isoformat(),
            "application_session_saved_utc": datetime.now(timezone.utc).isoformat(),
            "sensor_logging_started_utc": (
                self.sensor_logging_started_utc.isoformat() if self.sensor_logging_started_utc else None
            ),
            "sensor_logging_stopped_utc": (
                self.sensor_logging_stopped_utc.isoformat() if self.sensor_logging_stopped_utc else None
            ),
            "sensor_logging_active": self.sensor_logging_active,
            "selected_sensor_ids": sorted(self.selected_sensor_ids),
            "autosave_interval_s": self.autosave_interval_s,
            "total_elapsed_time_s": self.recording_elapsed_s(),
            "finalized": final,
            "files": {
                sensor_id: {
                    "data": self._sensor_csv_path(sensor_id).name,
                    "metadata": self._sensor_metadata_path(sensor_id).name,
                }
                for sensor_id in sorted(self.selected_sensor_ids)
            },
            "system_log": "system_log.csv",
        }
        (directory / "session_manifest.yaml").write_text(
            yaml.safe_dump(manifest, sort_keys=False),
            encoding="utf-8",
        )

    def recording_elapsed_s(self) -> float:
        if self.sensor_logging_started_monotonic is None:
            return 0.0
        end = time.monotonic() if self.sensor_logging_active else self.sensor_logging_stopped_monotonic
        if end is None:
            end = time.monotonic()
        return max(0.0, end - self.sensor_logging_started_monotonic)


class SessionRecorder(QtCore.QObject):
    """Thread-safe Qt facade for the background recorder worker."""

    message = QtCore.pyqtSignal(str)
    recording_changed = QtCore.pyqtSignal(bool)
    session_directory_changed = QtCore.pyqtSignal(str)
    save_completed = QtCore.pyqtSignal(str)

    def __init__(
        self,
        *,
        stream_hub: StreamHub,
        sensor_definitions: dict[str, SensorDefinition],
        base_directory: str | Path,
        autosave_interval_s: int = 30,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.stream_hub = stream_hub
        self._state = _RecorderState(
            sensor_definitions=sensor_definitions,
            base_directory=base_directory,
            autosave_interval_s=autosave_interval_s,
        )
        self._state_lock = threading.RLock()
        self._command_queue: queue.Queue[_RecorderCommand] = queue.Queue()
        self._stop_event = threading.Event()

        # Large bounded queues preserve normal high-rate operation while still
        # preventing unlimited memory growth if the disk becomes unavailable.
        self._frame_subscription = stream_hub.subscribe(
            "frames/*",
            queue_size=100_000,
            overflow_policy=OverflowPolicy.BLOCK,
            name="session-recorder-frames",
        )
        self._log_subscription = stream_hub.subscribe(
            "logs/*",
            queue_size=20_000,
            overflow_policy=OverflowPolicy.BLOCK,
            name="session-recorder-logs",
        )
        self._thread = threading.Thread(
            target=self._run,
            name="SessionRecorderWorker",
            daemon=True,
        )
        self._thread.start()

    # ------------------------------------------------------------------
    # Read-only compatibility properties used by MainWindow
    # ------------------------------------------------------------------
    @property
    def sensor_logging_active(self) -> bool:
        with self._state_lock:
            return self._state.sensor_logging_active

    @property
    def selected_sensor_ids(self) -> set[str]:
        with self._state_lock:
            return set(self._state.selected_sensor_ids)

    @property
    def session_directory(self) -> Path | None:
        with self._state_lock:
            return self._state.session_directory

    @property
    def autosave_interval_s(self) -> int:
        with self._state_lock:
            return self._state.autosave_interval_s

    # ------------------------------------------------------------------
    # Public command API. File work is performed in _run(), not here.
    # ------------------------------------------------------------------
    def set_base_directory(self, path: str | Path) -> None:
        self._submit("set_base_directory", path)

    def set_autosave_interval(self, seconds: int) -> None:
        self._submit("set_autosave_interval", seconds)

    def start_sensor_logging(self, sensor_ids: Iterable[str]) -> Path:
        return self._submit("start_sensor_logging", list(sensor_ids))

    def stop_sensor_logging(self) -> Path:
        return self._submit("stop_sensor_logging")

    def save_now(self) -> Path:
        return self._submit("save_now")

    def save_snapshot(self) -> Path:
        return self._submit("save_snapshot")

    def export_logs(self, destination: str | Path) -> Path:
        return self._submit("export_logs", destination)

    def ensure_session_directory(self) -> Path:
        return self._submit("ensure_session_directory")

    def finalize(self) -> Path:
        """Flush all data and stop the recorder thread during shutdown."""

        try:
            result = self._submit("finalize", timeout=15.0)
        finally:
            self._stop_event.set()
            self._thread.join(timeout=5.0)
            self._frame_subscription.close()
            self._log_subscription.close()
        return result

    def _submit(self, name: str, *args: Any, timeout: float = 10.0) -> Any:
        command = _RecorderCommand(name=name, args=args)
        self._command_queue.put(command)
        if not command.completed.wait(timeout):
            raise TimeoutError(f"Recorder command {name!r} did not finish within {timeout:g} seconds")
        if command.error is not None:
            raise command.error
        return command.result

    # ------------------------------------------------------------------
    # Recorder thread loop
    # ------------------------------------------------------------------
    def _run(self) -> None:
        next_autosave = time.monotonic() + self._state.autosave_interval_s
        last_frame_drop_count = 0

        while not self._stop_event.is_set():
            did_work = False

            # Commands are processed first so user save/stop requests remain
            # responsive even during a high-rate sensor stream.
            for _ in range(25):
                try:
                    command = self._command_queue.get_nowait()
                except queue.Empty:
                    break
                did_work = True
                self._execute_command(command)
                if command.name == "set_autosave_interval":
                    next_autosave = time.monotonic() + self._state.autosave_interval_s

            for envelope in self._frame_subscription.drain(2000):
                did_work = True
                if isinstance(envelope.payload, SensorFrame):
                    with self._state_lock:
                        self._state.ingest_frame(envelope.payload)

            for envelope in self._log_subscription.drain(1000):
                did_work = True
                if isinstance(envelope.payload, LogEvent):
                    with self._state_lock:
                        self._state.ingest_log(envelope.payload)

            now = time.monotonic()
            if now >= next_autosave:
                did_work = True
                try:
                    with self._state_lock:
                        directory = self._state.save_now()
                    self.message.emit(f"Autosaved session data to {directory}")
                except Exception as exc:
                    self.message.emit(f"Autosave failed: {exc}")
                next_autosave = now + self._state.autosave_interval_s

            if self._frame_subscription.dropped_messages > last_frame_drop_count:
                dropped = self._frame_subscription.dropped_messages - last_frame_drop_count
                last_frame_drop_count = self._frame_subscription.dropped_messages
                event = LogEvent(
                    timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                    elapsed_s=(time.monotonic_ns() - self.stream_hub.session_origin_monotonic_ns)
                    / 1_000_000_000.0,
                    level="ERROR",
                    source="recorder",
                    message=f"Recorder input queue overflowed; {dropped} frame(s) were dropped",
                    details={"total_dropped": last_frame_drop_count},
                )
                with self._state_lock:
                    self._state.ingest_log(event)
                self.stream_hub.publish_log(event)

            if not did_work:
                time.sleep(0.005)


    def _drain_stream_inputs(self) -> None:
        """Move all currently queued hub data into recorder state."""

        for envelope in self._frame_subscription.drain():
            if isinstance(envelope.payload, SensorFrame):
                with self._state_lock:
                    self._state.ingest_frame(envelope.payload)
        for envelope in self._log_subscription.drain():
            if isinstance(envelope.payload, LogEvent):
                with self._state_lock:
                    self._state.ingest_log(envelope.payload)

    def _execute_command(self, command: _RecorderCommand) -> None:
        try:
            # A manual save/stop/finalize should include every frame and log
            # that was already published before the button press.  Because the
            # command queue is processed before stream queues in the main loop,
            # explicitly drain those subscriptions first for persistence actions.
            if command.name in {
                "stop_sensor_logging",
                "save_now",
                "save_snapshot",
                "export_logs",
                "finalize",
            }:
                self._drain_stream_inputs()

            with self._state_lock:
                method = getattr(self._state, command.name)
                command.result = method(*command.args, **command.kwargs)
                active = self._state.sensor_logging_active
                directory = self._state.session_directory

            if command.name == "start_sensor_logging":
                self.recording_changed.emit(True)
                self.message.emit(f"Sensor logging started in {directory}")
            elif command.name == "stop_sensor_logging":
                self.recording_changed.emit(False)
                self.message.emit(f"Sensor logging stopped and saved to {directory}")
            elif command.name == "save_now":
                self.save_completed.emit(str(command.result))
                self.message.emit(f"Session saved to {command.result}")
            elif command.name == "save_snapshot":
                self.message.emit(f"Snapshot saved to {command.result}")
            elif command.name == "export_logs":
                self.message.emit(f"Log exported to {command.result}")
            elif command.name == "finalize":
                if active:
                    self.recording_changed.emit(False)
                self.message.emit(f"Session finalized at {command.result}")

            if directory is not None:
                self.session_directory_changed.emit(str(directory))
        except BaseException as exc:  # propagate exact failure to caller
            command.error = exc
        finally:
            command.completed.set()


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._") or "sensor"


def _unique_directory(path: Path) -> Path:
    if not path.exists():
        return path
    index = 2
    while True:
        candidate = path.with_name(f"{path.name}_{index}")
        if not candidate.exists():
            return candidate
        index += 1
