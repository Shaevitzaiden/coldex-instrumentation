from __future__ import annotations

"""Multi-device serial/ hardware lifecycle and command routing.

Every enabled device receives its own worker and QThread.  This is deliberately
simple and robust: one blocked serial instrument cannot stall another, and each
serial port has exactly one owner.
"""

import inspect
import queue
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from PyQt5 import QtCore

from ..data.models import (
    CommandResult,
    DeviceCommand,
    DeviceDefinition,
    DeviceStatus,
    LogEvent,
    SensorDefinition,
    SensorFrame,
)
from ..data.stream_hub import StreamHub


class DeviceWorker(QtCore.QObject):
    """Long-running worker that exclusively owns one communicator object.

    Important threading rule: this object runs in its device's QThread and is
    the only code that calls the communicator.  GUI/controller code places
    immutable commands in ``command_queue`` instead of touching serial methods.
    """

    finished = QtCore.pyqtSignal()

    def __init__(
        self,
        *,
        definition: DeviceDefinition,
        communicator: Any,
        command_queue: queue.Queue[DeviceCommand],
        stream_hub: StreamHub,
        channel_map: dict[str, str],
    ) -> None:
        super().__init__()
        self.definition = definition
        self.communicator = communicator
        self.command_queue = command_queue
        self.stream_hub = stream_hub
        self.channel_map = dict(channel_map)
        self._running = threading.Event()
        self._sequence = 0

    @QtCore.pyqtSlot()
    def run(self) -> None:
        self._running.set()
        connected = False
        try:
            self._connect_communicator()
            connected = self.communicator is not None
            self._publish_status(connected, "Connected" if connected else "No communicator supplied")
            self._log(
                "INFO" if connected else "WARNING",
                f"devices.{self.definition.device_id}",
                f"Device {self.definition.device_id} connected"
                if connected
                else f"Device {self.definition.device_id} has no communicator",
            )

            while self._running.is_set():
                did_work = self._process_commands()
                packets = self._read_packets()
                if packets:
                    did_work = True
                    for packet in packets:
                        self._dispatch_packet(packet)
                if not did_work:
                    # Avoid a hot spin while keeping command/sensor latency low.
                    time.sleep(0.002)
        except Exception as exc:
            self._log(
                "ERROR",
                f"devices.{self.definition.device_id}",
                f"Device worker stopped after error: {exc}",
            )
        finally:
            try:
                self._disconnect_communicator()
            except Exception as exc:
                self._log(
                    "ERROR",
                    f"devices.{self.definition.device_id}",
                    f"Error while closing communicator: {exc}",
                )
            self._publish_status(False, "Disconnected")
            self.finished.emit()

    def stop(self) -> None:
        self._running.clear()

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    def _process_commands(self) -> bool:
        processed = False
        # Bound each pass so a command flood cannot starve incoming telemetry.
        for _ in range(50):
            try:
                command = self.command_queue.get_nowait()
            except queue.Empty:
                break
            processed = True
            self._execute_command(command)
        return processed

    def _execute_command(self, command: DeviceCommand) -> None:
        result_payload = dict(command.payload)
        try:
            if self.communicator is None:
                raise RuntimeError(f"No communicator attached to {self.definition.device_id}")

            if command.command_type == "set_element_state":
                self._execute_element_command(command.payload)
            elif hasattr(self.communicator, "execute_command"):
                # Generic extension point for future non-valve instruments.
                self.communicator.execute_command(command)
            else:
                raise TypeError(
                    f"Device {self.definition.device_id} cannot execute command type "
                    f"{command.command_type!r}"
                )

            result = CommandResult(
                device_id=self.definition.device_id,
                command_type=command.command_type,
                success=True,
                message="Command completed",
                payload=result_payload,
                command_id=command.command_id,
            )
            self._log(
                "INFO",
                f"devices.{self.definition.device_id}.command",
                f"Command completed: {command.command_type}",
                details={**result_payload, "origin": command.origin},
            )
        except Exception as exc:
            result = CommandResult(
                device_id=self.definition.device_id,
                command_type=command.command_type,
                success=False,
                message=str(exc),
                payload=result_payload,
                command_id=command.command_id,
            )
            self._log(
                "ERROR",
                f"devices.{self.definition.device_id}.command",
                f"Command failed: {command.command_type}: {exc}",
                details={**result_payload, "origin": command.origin},
            )
        self.stream_hub.publish_command_result(result)

    def _execute_element_command(self, payload: dict[str, Any]) -> None:
        element_id = str(payload["element_id"])
        is_active = bool(payload["is_active"])
        relay_number = payload.get("relay_number")
        metadata = dict(payload.get("metadata", {}))

        if hasattr(self.communicator, "set_element_state"):
            self.communicator.set_element_state(
                element_id=element_id,
                element_type=str(payload.get("element_type", "unknown")),
                is_active=is_active,
                relay_number=relay_number,
                metadata=metadata,
            )
        elif hasattr(self.communicator, "set_valve_state"):
            self.communicator.set_valve_state(
                valve_id=element_id,
                is_open=is_active,
                command_id=relay_number,
                metadata=metadata,
            )
        else:
            raise TypeError(
                "Communicator must define set_element_state(...), "
                "set_valve_state(...), or execute_command(...)"
            )

    # ------------------------------------------------------------------
    # Telemetry packet reading and normalization
    # ------------------------------------------------------------------
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
            self._log(
                "ERROR",
                f"devices.{self.definition.device_id}.read",
                f"Read error: {exc}",
            )
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
            self.stream_hub.publish_frame(self._normalize_existing_frame(packet))
            return
        if isinstance(packet, LogEvent):
            self.stream_hub.publish_log(packet)
            return
        if not isinstance(packet, dict):
            self._log(
                "DEBUG",
                f"devices.{self.definition.device_id}.packet",
                f"Ignored unsupported packet: {packet!r}",
            )
            return

        packet_type = str(packet.get("type", packet.get("kind", "sensor_frame"))).lower()
        if packet_type in {"sensor", "sample", "sensor_frame", "samples", "data"}:
            self._publish_sensor_packet(packet)
            return
        if packet_type in {"log", "message", "debug"}:
            self._log(
                str(packet.get("level", "INFO")),
                str(packet.get("source", f"microcontroller.{self.definition.device_id}")),
                str(packet.get("message", packet.get("text", ""))),
                details=dict(packet.get("details", {})),
            )
            return
        if packet_type in {"relay_result", "ack", "command_result"}:
            payload = dict(packet)
            payload.setdefault("device_id", self.definition.device_id)
            self.stream_hub.publish_command_result(payload)
            return
        self._log(
            "DEBUG",
            f"devices.{self.definition.device_id}.packet",
            f"Unhandled packet type {packet_type}: {packet!r}",
        )

    def _publish_sensor_packet(self, packet: dict[str, Any]) -> None:
        values = packet.get("values")
        if values is None and "channel" in packet and "value" in packet:
            values = {str(packet["channel"]): packet["value"]}
        if not isinstance(values, dict):
            self._log(
                "WARNING",
                f"devices.{self.definition.device_id}.packet",
                f"Sensor packet missing values mapping: {packet!r}",
            )
            return

        numeric_values: dict[str, float] = {}
        for local_channel, value in values.items():
            try:
                global_sensor_id = self._qualify_channel(str(local_channel))
                numeric_values[global_sensor_id] = float(value)
            except (TypeError, ValueError):
                self._log(
                    "WARNING",
                    f"devices.{self.definition.device_id}.packet",
                    f"Non-numeric sample ignored for {local_channel}: {value!r}",
                )
        if not numeric_values:
            return

        self._sequence += 1
        host_ns = time.monotonic_ns()
        raw_sequence = packet.get("sequence")
        normalized_sequence = self._sequence if raw_sequence is None else int(raw_sequence)
        frame = SensorFrame(
            elapsed_s=(host_ns - self.stream_hub.session_origin_monotonic_ns) / 1_000_000_000.0,
            timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            values=numeric_values,
            source_id=self.definition.device_id,
            host_received_monotonic_ns=host_ns,
            device_timestamp=packet.get("device_timestamp", packet.get("timestamp")),
            sequence=normalized_sequence,
            metadata={
                **dict(packet.get("metadata", {})),
                "device_id": self.definition.device_id,
            },
        )
        self.stream_hub.publish_frame(frame)

    def _normalize_existing_frame(self, frame: SensorFrame) -> SensorFrame:
        host_ns = frame.host_received_monotonic_ns or time.monotonic_ns()
        return SensorFrame(
            elapsed_s=(host_ns - self.stream_hub.session_origin_monotonic_ns) / 1_000_000_000.0,
            timestamp_utc=frame.timestamp_utc
            or datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            values={self._qualify_channel(channel): float(value) for channel, value in frame.values.items()},
            source_id=frame.source_id or self.definition.device_id,
            host_received_monotonic_ns=host_ns,
            device_timestamp=frame.device_timestamp,
            sequence=frame.sequence,
            metadata={**dict(frame.metadata), "device_id": self.definition.device_id},
        )

    def _qualify_channel(self, channel: str) -> str:
        # A driver may already return a globally qualified ID.  Otherwise use
        # the explicit sensor configuration map, then a deterministic fallback.
        if channel in self.channel_map:
            return self.channel_map[channel]
        if "." in channel:
            return channel
        return f"{self.definition.device_id}.{channel}"

    # ------------------------------------------------------------------
    # Communicator lifecycle helpers
    # ------------------------------------------------------------------
    def _connect_communicator(self) -> None:
        if self.communicator is None:
            return
        for name in ("connect", "open", "start"):
            method = getattr(self.communicator, name, None)
            if not callable(method):
                continue
            # Prefer passing configured connection fields when accepted.  Fall
            # back to a no-argument call for preconfigured communicator objects.
            try:
                signature = inspect.signature(method)
                accepts_kwargs = any(
                    parameter.kind is inspect.Parameter.VAR_KEYWORD
                    for parameter in signature.parameters.values()
                )
                named = {
                    key: value
                    for key, value in self.definition.connection.items()
                    if key in signature.parameters or accepts_kwargs
                }
                method(**named)
            except (TypeError, ValueError):
                method()
            return

    def _disconnect_communicator(self) -> None:
        if self.communicator is None:
            return
        for name in ("disconnect", "close", "stop"):
            method = getattr(self.communicator, name, None)
            if callable(method):
                method()
                return

    def _publish_status(self, connected: bool, message: str) -> None:
        self.stream_hub.publish_device_status(
            DeviceStatus(
                device_id=self.definition.device_id,
                connected=connected,
                message=message,
                details=dict(self.definition.metadata),
            )
        )

    def _log(
        self,
        level: str,
        source: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        host_ns = time.monotonic_ns()
        self.stream_hub.publish_log(
            LogEvent(
                timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                elapsed_s=(host_ns - self.stream_hub.session_origin_monotonic_ns) / 1_000_000_000.0,
                level=level.upper(),
                source=source,
                message=message,
                details=dict(details or {}),
            )
        )


class SerialDeviceService:
    """Owns the queue, worker, and QThread for one device definition."""

    def __init__(
        self,
        *,
        definition: DeviceDefinition,
        communicator: Any,
        stream_hub: StreamHub,
        channel_map: dict[str, str],
        parent: QtCore.QObject | None = None,
    ) -> None:
        self.definition = definition
        self.communicator = communicator
        self.stream_hub = stream_hub
        self.command_queue: queue.Queue[DeviceCommand] = queue.Queue()
        self.thread = QtCore.QThread(parent)
        self.worker = DeviceWorker(
            definition=definition,
            communicator=communicator,
            command_queue=self.command_queue,
            stream_hub=stream_hub,
            channel_map=channel_map,
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)

    def start(self) -> None:
        if not self.thread.isRunning():
            self.thread.start()

    def stop(self, timeout_ms: int = 3000) -> None:
        self.worker.stop()
        if not self.thread.wait(timeout_ms):
            # Last resort only; normal communicators should honor short read
            # timeouts so the worker exits cleanly.
            self.thread.requestInterruption()
            if not self.thread.wait(1000):
                self.thread.terminate()
                self.thread.wait(1000)

    def submit(self, command: DeviceCommand) -> None:
        self.command_queue.put(command)


class DeviceManager(QtCore.QObject):
    """Facade that starts devices and routes addressed commands."""

    def __init__(
        self,
        *,
        device_definitions: dict[str, DeviceDefinition],
        sensor_definitions: dict[str, SensorDefinition],
        communicators: dict[str, Any] | None,
        stream_hub: StreamHub,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.device_definitions = dict(device_definitions)
        self.sensor_definitions = dict(sensor_definitions)
        self.communicators = dict(communicators or {})
        self.stream_hub = stream_hub
        self.services: dict[str, SerialDeviceService] = {}

        command_targets = [d.device_id for d in self.device_definitions.values() if d.command_target]
        self.default_command_device_id = command_targets[0] if command_targets else next(
            iter(self.device_definitions), "controller"
        )
        self._build_services()

    def _build_services(self) -> None:
        for definition in self.device_definitions.values():
            if not definition.enabled:
                continue
            communicator = self.communicators.get(definition.communicator_key or definition.device_id)
            channel_map = {
                sensor.source_channel: sensor.sensor_id
                for sensor in self.sensor_definitions.values()
                if sensor.source_device == definition.device_id
            }
            self.services[definition.device_id] = SerialDeviceService(
                definition=definition,
                communicator=communicator,
                stream_hub=self.stream_hub,
                channel_map=channel_map,
                parent=self,
            )

    def start(self) -> None:
        for service in self.services.values():
            service.start()

    def stop(self, timeout_ms_per_device: int = 3000) -> None:
        for service in self.services.values():
            service.stop(timeout_ms_per_device)

    def set_communicator(self, device_id: str, communicator: Any | None) -> None:
        """Replace one communicator, rebuilding only its service."""

        definition = self.device_definitions[device_id]
        old = self.services.pop(device_id, None)
        if old is not None:
            old.stop()
        self.communicators[definition.communicator_key or device_id] = communicator
        channel_map = {
            sensor.source_channel: sensor.sensor_id
            for sensor in self.sensor_definitions.values()
            if sensor.source_device == device_id
        }
        service = SerialDeviceService(
            definition=definition,
            communicator=communicator,
            stream_hub=self.stream_hub,
            channel_map=channel_map,
            parent=self,
        )
        self.services[device_id] = service
        service.start()

    def submit_command(self, command: DeviceCommand) -> None:
        try:
            service = self.services[command.device_id]
        except KeyError as exc:
            raise KeyError(f"No enabled device service named {command.device_id!r}") from exc
        service.submit(command)

    # The next two methods intentionally match PneumaticController's existing
    # communicator interface, making DeviceManager a drop-in replacement.
    def set_element_state(
        self,
        *,
        element_id: str,
        element_type: str,
        is_active: bool,
        relay_number: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        metadata = dict(metadata or {})
        device_id = str(metadata.get("device_id", self.default_command_device_id))
        command = DeviceCommand(
            device_id=device_id,
            command_type="set_element_state",
            payload={
                "element_id": element_id,
                "element_type": element_type,
                "is_active": bool(is_active),
                "relay_number": relay_number,
                "metadata": metadata,
            },
            origin=str(metadata.get("origin", "user")),
            command_id=str(uuid.uuid4()),
            created_monotonic_ns=time.monotonic_ns(),
        )
        self.submit_command(command)
        self.stream_hub.publish_log(
            LogEvent(
                timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                elapsed_s=(time.monotonic_ns() - self.stream_hub.session_origin_monotonic_ns)
                / 1_000_000_000.0,
                level="INFO",
                source="user.command",
                message=(
                    f"User requested {element_id} -> "
                    f"{'ACTIVE/OPEN' if is_active else 'INACTIVE/CLOSED'} on {device_id}"
                ),
                details={
                    "device_id": device_id,
                    "element_id": element_id,
                    "element_type": element_type,
                    "relay_number": relay_number,
                    "is_active": bool(is_active),
                    "command_id": command.command_id,
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
