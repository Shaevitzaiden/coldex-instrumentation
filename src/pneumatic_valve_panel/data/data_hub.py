from __future__ import annotations

"""Qt-facing view of the central StreamHub.

``DataHub`` is intentionally no longer the high-rate transport itself.  It is a
small GUI cache/signal facade fed by :class:`QtDataBridge`.  Non-GUI consumers
should subscribe to ``StreamHub`` directly.
"""

import time
from typing import Any

from PyQt5 import QtCore

from .models import CommandResult, DeviceStatus, LogEvent, SensorFrame, utc_now_iso
from .stream_hub import StreamHub


class DataHub(QtCore.QObject):
    """GUI-thread broadcast point for normalized data and application events."""

    frame_received = QtCore.pyqtSignal(object)  # SensorFrame
    log_received = QtCore.pyqtSignal(object)  # LogEvent
    connection_changed = QtCore.pyqtSignal(bool)  # aggregate: any device connected
    device_connection_changed = QtCore.pyqtSignal(str, bool)
    relay_result_received = QtCore.pyqtSignal(object)

    def __init__(
        self,
        *,
        stream_hub: StreamHub,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.stream_hub = stream_hub
        self._started_monotonic = time.monotonic()
        self.latest_values: dict[str, float] = {}
        self.latest_frame: SensorFrame | None = None
        self.device_connections: dict[str, bool] = {}
        self.connected = False

    @QtCore.pyqtSlot(object)
    def publish_frame(self, frame: SensorFrame) -> None:
        """Receive a frame from QtDataBridge and notify GUI widgets."""

        self.latest_frame = frame
        self.latest_values.update(frame.values)
        self.frame_received.emit(frame)

    @QtCore.pyqtSlot(object)
    def publish_log_event(self, event: LogEvent) -> None:
        """Receive an already-published log event from QtDataBridge."""

        self.log_received.emit(event)

    @QtCore.pyqtSlot(object)
    def publish_device_status(self, status: DeviceStatus) -> None:
        self.device_connections[status.device_id] = bool(status.connected)
        self.device_connection_changed.emit(status.device_id, bool(status.connected))
        aggregate = any(self.device_connections.values())
        if aggregate != self.connected:
            self.connected = aggregate
            self.connection_changed.emit(self.connected)

    @QtCore.pyqtSlot(object)
    def publish_relay_result(self, result: CommandResult | dict[str, Any]) -> None:
        self.relay_result_received.emit(result)

    def log(
        self,
        message: str,
        *,
        level: str = "INFO",
        source: str = "application",
        details: dict[str, Any] | None = None,
    ) -> LogEvent:
        """Publish a log into the central hub from any GUI action."""

        event = LogEvent(
            timestamp_utc=utc_now_iso(),
            elapsed_s=time.monotonic() - self._started_monotonic,
            level=level.upper(),
            source=source,
            message=message,
            details=dict(details or {}),
        )
        self.stream_hub.publish_log(event)
        return event
