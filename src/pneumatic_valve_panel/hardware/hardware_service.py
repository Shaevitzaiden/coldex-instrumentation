from __future__ import annotations

import inspect
import queue
import threading
import time
from datetime import datetime, timezone
from typing import Any, Iterable

from PyQt5 import QtCore

from ..data.models import LogEvent, SensorFrame


class HardwareWorker(QtCore.QObject):
    """Long-running worker that exclusively owns the communicator.

    The worker intentionally uses a Python ``queue.Queue`` for commands because
    its polling loop occupies the QThread. GUI code never touches the serial
    object; it only appends command dictionaries to the thread-safe queue.
    """

    frame_received = QtCore.pyqtSignal(object)
    log_event = QtCore.pyqtSignal(object)
    relay_result = QtCore.pyqtSignal(object)
    connection_changed = QtCore.pyqtSignal(bool)
    finished = QtCore.pyqtSignal()

    def __init__(self, communicator: Any, command_queue: queue.Queue[dict[str, Any]]) -> None:
        super().__init__()
        self.communicator = communicator
        self.command_queue = command_queue
        self._running = threading.Event()
        self._started_monotonic = time.monotonic()
        self._sequence = 0

    @QtCore.pyqtSlot()
    def run(self) -> None:
        self._running.set()
        self._started_monotonic = time.monotonic()
        connected = False
        try:
            self._call_optional(("connect", "open", "start"))
            connected = self.communicator is not None
            self.connection_changed.emit(connected)
            self._emit_log(
                "INFO" if connected else "WARNING",
                "hardware",
                "Hardware communicator connected" if connected else "No communicator supplied; hardware commands will fail",
            )

            while self._running.is_set():
                did_work = self._process_commands()
                packets = self._read_packets()
                if packets:
                    did_work = True
                    for packet in packets:
                        self._dispatch_packet(packet)
                if not did_work:
                    time.sleep(0.005)
        except Exception as exc:  # defensive boundary around user communicator
            self._emit_log("ERROR", "hardware", f"Hardware worker stopped after error: {exc}")
        finally:
            try:
                self._call_optional(("disconnect", "close", "stop"))
            except Exception as exc:
                self._emit_log("ERROR", "hardware", f"Error while closing communicator: {exc}")
            self.connection_changed.emit(False)
            self.finished.emit()

    def stop(self) -> None:
        self._running.clear()

    def _process_commands(self) -> bool:
        processed = False
        for _ in range(50):
            try:
                command = self.command_queue.get_nowait()
            except queue.Empty:
                break
            processed = True
            self._execute_command(command)
        return processed

    def _execute_command(self, command: dict[str, Any]) -> None:
        element_id = str(command["element_id"])
        is_active = bool(command["is_active"])
        relay_number = command.get("relay_number")
        result = {
            "element_id": element_id,
            "relay_number": relay_number,
            "is_active": is_active,
            "success": False,
            "message": "",
        }
        try:
            if self.communicator is None:
                raise RuntimeError("No communicator attached")
            if hasattr(self.communicator, "set_element_state"):
                self.communicator.set_element_state(
                    element_id=element_id,
                    element_type=str(command.get("element_type", "unknown")),
                    is_active=is_active,
                    relay_number=relay_number,
                    metadata=dict(command.get("metadata", {})),
                )
            elif hasattr(self.communicator, "set_valve_state"):
                self.communicator.set_valve_state(
                    valve_id=element_id,
                    is_open=is_active,
                    command_id=relay_number,
                    metadata=dict(command.get("metadata", {})),
                )
            else:
                raise TypeError("Communicator must define set_element_state(...) or set_valve_state(...)")
            result["success"] = True
            result["message"] = "Command completed"
            self._emit_log(
                "INFO",
                "hardware.command",
                f"Relay command completed: {element_id} -> {'ACTIVE/OPEN' if is_active else 'INACTIVE/CLOSED'}",
                details=result,
            )
        except Exception as exc:
            result["message"] = str(exc)
            self._emit_log(
                "ERROR",
                "hardware.command",
                f"Relay command failed: {element_id}: {exc}",
                details=result,
            )
        self.relay_result.emit(result)

    def _read_packets(self) -> list[Any]:
        if self.communicator is None:
            return []
        reader = None
        for name in ("read_available_packets", "read_packets", "poll", "read_packet"):
            candidate = getattr(self.communicator, name, None)
            if callable(candidate):
                reader = candidate
                break
        if reader is None:
            return []
        try:
            try:
                result = reader(timeout_s=0.01)
            except TypeError:
                try:
                    result = reader(0.01)
                except TypeError:
                    result = reader()
        except Exception as exc:
            self._emit_log("ERROR", "hardware.read", f"Read error: {exc}")
            time.sleep(0.05)
            return []
        if result is None:
            return []
        if isinstance(result, (list, tuple)):
            return list(result)
        if isinstance(result, Iterable) and not isinstance(result, (str, bytes, dict, SensorFrame)):
            return list(result)
        return [result]

    def _dispatch_packet(self, packet: Any) -> None:
        if isinstance(packet, SensorFrame):
            self.frame_received.emit(packet)
            return
        if isinstance(packet, LogEvent):
            self.log_event.emit(packet)
            return
        if not isinstance(packet, dict):
            self._emit_log("DEBUG", "hardware.packet", f"Ignored unsupported packet: {packet!r}")
            return

        packet_type = str(packet.get("type", packet.get("kind", "sensor_frame"))).lower()
        if packet_type in {"sensor", "sample", "sensor_frame", "samples", "data"}:
            values = packet.get("values")
            if values is None and "channel" in packet and "value" in packet:
                values = {str(packet["channel"]): packet["value"]}
            if not isinstance(values, dict):
                self._emit_log("WARNING", "hardware.packet", f"Sensor packet missing values mapping: {packet!r}")
                return
            numeric_values: dict[str, float] = {}
            for channel, value in values.items():
                try:
                    numeric_values[str(channel)] = float(value)
                except (TypeError, ValueError):
                    self._emit_log("WARNING", "hardware.packet", f"Non-numeric sample ignored for {channel}: {value!r}")
            if not numeric_values:
                return
            self._sequence += 1
            frame = SensorFrame(
                elapsed_s=time.monotonic() - self._started_monotonic,
                timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                values=numeric_values,
                device_timestamp=packet.get("device_timestamp", packet.get("timestamp")),
                sequence=int(packet.get("sequence", self._sequence)),
                metadata=dict(packet.get("metadata", {})),
            )
            self.frame_received.emit(frame)
            return

        if packet_type in {"log", "message", "debug"}:
            self._emit_log(
                str(packet.get("level", "INFO")),
                str(packet.get("source", "microcontroller")),
                str(packet.get("message", packet.get("text", ""))),
                details=dict(packet.get("details", {})),
            )
            return

        if packet_type in {"relay_result", "ack", "command_result"}:
            self.relay_result.emit(dict(packet))
            return

        self._emit_log("DEBUG", "hardware.packet", f"Unhandled packet type {packet_type}: {packet!r}")

    def _call_optional(self, names: tuple[str, ...]) -> Any:
        if self.communicator is None:
            return None
        for name in names:
            method = getattr(self.communicator, name, None)
            if callable(method):
                return method()
        return None

    def _emit_log(
        self,
        level: str,
        source: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.log_event.emit(
            LogEvent(
                timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                elapsed_s=time.monotonic() - self._started_monotonic,
                level=level.upper(),
                source=source,
                message=message,
                details=dict(details or {}),
            )
        )


class HardwareService(QtCore.QObject):
    """Thread-safe facade used by controllers and the main window."""

    frame_received = QtCore.pyqtSignal(object)
    log_event = QtCore.pyqtSignal(object)
    relay_result = QtCore.pyqtSignal(object)
    connection_changed = QtCore.pyqtSignal(bool)

    def __init__(self, communicator: Any = None, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.communicator = communicator
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._thread: QtCore.QThread | None = None
        self._worker: HardwareWorker | None = None
        self._started_monotonic = time.monotonic()

    def start(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            return
        self._thread = QtCore.QThread(self)
        self._worker = HardwareWorker(self.communicator, self._queue)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.frame_received.connect(self.frame_received)
        self._worker.log_event.connect(self.log_event)
        self._worker.relay_result.connect(self.relay_result)
        self._worker.connection_changed.connect(self.connection_changed)
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()

    def stop(self, timeout_ms: int = 3000) -> None:
        worker = self._worker
        thread = self._thread
        if worker is None or thread is None:
            return
        worker.stop()
        if not thread.wait(timeout_ms):
            self.log_event.emit(
                LogEvent(
                    timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                    elapsed_s=time.monotonic() - self._started_monotonic,
                    level="WARNING",
                    source="hardware",
                    message="Hardware thread did not stop before timeout; terminating as a last resort",
                )
            )
            thread.requestInterruption()
            if not thread.wait(1000):
                thread.terminate()
                thread.wait(1000)
        self._worker = None
        self._thread = None

    def set_communicator(self, communicator: Any | None) -> None:
        was_running = self._thread is not None and self._thread.isRunning()
        if was_running:
            self.stop()
        self.communicator = communicator
        if was_running:
            self.start()

    def set_element_state(
        self,
        *,
        element_id: str,
        element_type: str,
        is_active: bool,
        relay_number: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        command = {
            "element_id": element_id,
            "element_type": element_type,
            "is_active": bool(is_active),
            "relay_number": relay_number,
            "metadata": dict(metadata or {}),
        }
        self._queue.put(command)
        self.log_event.emit(
            LogEvent(
                timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                elapsed_s=time.monotonic() - self._started_monotonic,
                level="INFO",
                source="user.command",
                message=f"User requested {element_id} -> {'ACTIVE/OPEN' if is_active else 'INACTIVE/CLOSED'}",
                details={
                    "element_id": element_id,
                    "element_type": element_type,
                    "relay_number": relay_number,
                    "is_active": bool(is_active),
                },
            )
        )

    def set_valve_state(
        self,
        *,
        valve_id: str,
        is_open: bool,
        command_id: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.set_element_state(
            element_id=valve_id,
            element_type=str((metadata or {}).get("element_type", "unknown")),
            is_active=is_open,
            relay_number=int(command_id) if command_id is not None else None,
            metadata=metadata,
        )
