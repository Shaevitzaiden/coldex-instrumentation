from __future__ import annotations

import csv
import json
import re
import shutil
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml
from PyQt5 import QtCore

from ..data.models import LogEvent, SensorDefinition, SensorFrame


class SessionRecorder(QtCore.QObject):
    """Incremental session recorder with periodic autosave and snapshots.

    Logs are buffered from application startup. Sensor rows are retained only for
    channels selected when sensor logging starts. All channels from one
    ``SensorFrame`` keep the same synchronized host timestamp.
    """

    message = QtCore.pyqtSignal(str)
    recording_changed = QtCore.pyqtSignal(bool)
    session_directory_changed = QtCore.pyqtSignal(str)
    save_completed = QtCore.pyqtSignal(str)

    def __init__(
        self,
        *,
        sensor_definitions: dict[str, SensorDefinition],
        base_directory: str | Path,
        autosave_interval_s: int = 30,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.sensor_definitions = dict(sensor_definitions)
        self.base_directory = Path(base_directory)
        self.autosave_interval_s = max(5, int(autosave_interval_s))

        self.app_started_utc = datetime.now(timezone.utc)
        self.app_started_monotonic = time.monotonic()
        self.session_directory: Path | None = None
        self.sensor_logging_active = False
        self.selected_sensor_ids: set[str] = set()
        self.sensor_logging_started_utc: datetime | None = None
        self.sensor_logging_started_elapsed_s: float | None = None
        self.sensor_logging_started_monotonic: float | None = None
        self.sensor_logging_stopped_monotonic: float | None = None
        self.sensor_logging_stopped_utc: datetime | None = None
        self._frame_elapsed_origin: float | None = None

        self._pending_logs: list[LogEvent] = []
        self._pending_sensor_rows: dict[str, list[tuple[str, float, float, Any, Any]]] = defaultdict(list)
        self._sample_counts: dict[str, int] = defaultdict(int)
        self._first_sensor_elapsed: dict[str, float] = {}
        self._last_sensor_elapsed: dict[str, float] = {}
        self._created_sensor_files: set[str] = set()
        self._finalized = False

        self._autosave_timer = QtCore.QTimer(self)
        self._autosave_timer.timeout.connect(self.autosave)
        self._autosave_timer.start(self.autosave_interval_s * 1000)

    @QtCore.pyqtSlot(object)
    def on_log_event(self, event: LogEvent) -> None:
        self._pending_logs.append(event)

    @QtCore.pyqtSlot(object)
    def on_sensor_frame(self, frame: SensorFrame) -> None:
        if not self.sensor_logging_active:
            return
        for sensor_id in self.selected_sensor_ids:
            if sensor_id not in frame.values:
                continue
            value = float(frame.values[sensor_id])
            if self._frame_elapsed_origin is None:
                self._frame_elapsed_origin = float(frame.elapsed_s)
            elapsed = float(frame.elapsed_s) - self._frame_elapsed_origin
            self._pending_sensor_rows[sensor_id].append(
                (
                    frame.timestamp_utc,
                    elapsed,
                    value,
                    frame.sequence,
                    frame.device_timestamp,
                )
            )
            self._sample_counts[sensor_id] += 1
            self._first_sensor_elapsed.setdefault(sensor_id, elapsed)
            self._last_sensor_elapsed[sensor_id] = elapsed

    def set_base_directory(self, path: str | Path) -> None:
        if self.session_directory is not None:
            raise RuntimeError("The session directory has already been created and cannot be moved")
        self.base_directory = Path(path)

    def set_autosave_interval(self, seconds: int) -> None:
        self.autosave_interval_s = max(5, int(seconds))
        self._autosave_timer.start(self.autosave_interval_s * 1000)
        self.message.emit(f"Autosave interval set to {self.autosave_interval_s} seconds")

    def start_sensor_logging(self, sensor_ids: Iterable[str]) -> Path:
        if self.sensor_logging_active:
            raise RuntimeError("Sensor logging is already active")
        if self.sensor_logging_started_utc is not None:
            raise RuntimeError("This application session already contains a completed logging period")
        selected = {str(sensor_id) for sensor_id in sensor_ids}
        unknown = selected.difference(self.sensor_definitions)
        if unknown:
            raise ValueError(f"Unknown sensor IDs: {sorted(unknown)}")
        selected = {
            sensor_id
            for sensor_id in selected
            if self.sensor_definitions[sensor_id].enabled
        }
        if not selected:
            raise ValueError("Select at least one enabled sensor to log")

        directory = self.ensure_session_directory()
        self.selected_sensor_ids = selected
        self.sensor_logging_active = True
        self.sensor_logging_started_utc = datetime.now(timezone.utc)
        self.sensor_logging_started_elapsed_s = time.monotonic() - self.app_started_monotonic
        self.sensor_logging_started_monotonic = time.monotonic()
        self.sensor_logging_stopped_monotonic = None
        self.sensor_logging_stopped_utc = None
        self._frame_elapsed_origin = None
        self._finalized = False
        for sensor_id in selected:
            self._ensure_sensor_file(sensor_id)
        self._write_manifest(final=False)
        self.recording_changed.emit(True)
        self.message.emit(f"Sensor logging started for {len(selected)} channel(s)")
        return directory

    def stop_sensor_logging(self) -> Path:
        self.sensor_logging_active = False
        self.sensor_logging_stopped_monotonic = time.monotonic()
        self.sensor_logging_stopped_utc = datetime.now(timezone.utc)
        directory = self.save_now()
        self.recording_changed.emit(False)
        self.message.emit("Sensor logging stopped and current data saved")
        return directory

    @QtCore.pyqtSlot()
    def autosave(self) -> None:
        if self.session_directory is None and not self.sensor_logging_active:
            return
        if not self._pending_logs and not any(self._pending_sensor_rows.values()):
            return
        try:
            directory = self.save_now()
            self.message.emit(f"Autosaved session data to {directory}")
        except Exception as exc:
            self.message.emit(f"Autosave failed: {exc}")

    def save_now(self) -> Path:
        directory = self.ensure_session_directory()
        self._flush_logs()
        self._flush_sensor_rows()
        self._write_metadata_files(final=False)
        self._write_manifest(final=False)
        self.save_completed.emit(str(directory))
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
        self.message.emit(f"Snapshot saved to {snapshot_dir}")
        return snapshot_dir

    def export_logs(self, destination: str | Path) -> Path:
        self.save_now()
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        source = self.ensure_session_directory() / "system_log.csv"
        shutil.copy2(source, destination)
        self.message.emit(f"Log exported to {destination}")
        return destination

    def finalize(self) -> Path:
        if self._finalized:
            return self.ensure_session_directory()
        if self.sensor_logging_active:
            self.sensor_logging_active = False
            self.sensor_logging_stopped_monotonic = time.monotonic()
            self.sensor_logging_stopped_utc = datetime.now(timezone.utc)
            self.recording_changed.emit(False)
        directory = self.ensure_session_directory()
        self._flush_logs()
        self._flush_sensor_rows()
        self._write_metadata_files(final=True)
        self._write_manifest(final=True)
        self._autosave_timer.stop()
        self._finalized = True
        self.message.emit(f"Session finalized at {directory}")
        return directory

    def ensure_session_directory(self) -> Path:
        if self.session_directory is not None:
            return self.session_directory
        self.base_directory.mkdir(parents=True, exist_ok=True)
        stamp = self.app_started_utc.astimezone().strftime("%Y-%m-%d_%H-%M-%S")
        directory = _unique_directory(self.base_directory / stamp)
        directory.mkdir(parents=True, exist_ok=False)
        self.session_directory = directory
        self.session_directory_changed.emit(str(directory))
        return directory

    def _flush_logs(self) -> None:
        if not self._pending_logs:
            return
        path = self.ensure_session_directory() / "system_log.csv"
        write_header = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if write_header:
                writer.writerow(["timestamp_utc", "elapsed_app_s", "level", "source", "message", "details_json"])
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
            path = self._sensor_csv_path(sensor_id)
            with path.open("a", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                for timestamp_utc, elapsed_s, value, sequence, device_timestamp in rows:
                    writer.writerow(
                        [
                            timestamp_utc,
                            f"{elapsed_s:.9f}",
                            f"{value:.12g}",
                            "" if sequence is None else sequence,
                            "" if device_timestamp is None else device_timestamp,
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
                handle.write(f"# unit: {definition.unit}\n")
                handle.write(f"# configured_sampling_frequency_hz: {definition.expected_sampling_hz if definition.expected_sampling_hz is not None else ''}\n")
                handle.write(f"# application_session_started_utc: {self.app_started_utc.isoformat()}\n")
                writer = csv.writer(handle)
                writer.writerow(["timestamp_utc", "elapsed_s", "value", "sequence", "device_timestamp"])
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
            total_elapsed = self._recording_elapsed_s()
            metadata = {
                "sensor_id": definition.sensor_id,
                "sensor_label": definition.label,
                "unit": definition.unit,
                "configured_sampling_frequency_hz": definition.expected_sampling_hz,
                "estimated_sampling_frequency_hz": actual_hz,
                "sample_count": count,
                "total_elapsed_time_s": total_elapsed,
                "sensor_logging_started_utc": self.sensor_logging_started_utc.isoformat() if self.sensor_logging_started_utc else None,
                "sensor_logging_stopped_utc": self.sensor_logging_stopped_utc.isoformat() if self.sensor_logging_stopped_utc else None,
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
            "schema_version": 1,
            "application_session_started_utc": self.app_started_utc.isoformat(),
            "application_session_saved_utc": datetime.now(timezone.utc).isoformat(),
            "sensor_logging_started_utc": self.sensor_logging_started_utc.isoformat() if self.sensor_logging_started_utc else None,
            "sensor_logging_stopped_utc": self.sensor_logging_stopped_utc.isoformat() if self.sensor_logging_stopped_utc else None,
            "sensor_logging_active": self.sensor_logging_active,
            "selected_sensor_ids": sorted(self.selected_sensor_ids),
            "autosave_interval_s": self.autosave_interval_s,
            "total_elapsed_time_s": self._recording_elapsed_s(),
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

    def _recording_elapsed_s(self) -> float:
        if self.sensor_logging_started_monotonic is None:
            return 0.0
        end = time.monotonic() if self.sensor_logging_active else self.sensor_logging_stopped_monotonic
        if end is None:
            end = time.monotonic()
        return max(0.0, end - self.sensor_logging_started_monotonic)


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
