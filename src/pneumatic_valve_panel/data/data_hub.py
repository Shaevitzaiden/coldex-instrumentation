from __future__ import annotations

import time
from typing import Any

from PyQt5 import QtCore

from .models import LogEvent, SensorFrame, utc_now_iso


class DataHub(QtCore.QObject):
    """GUI-thread broadcast point for normalized hardware data and application logs."""

    frame_received = QtCore.pyqtSignal(object)  # SensorFrame
    log_received = QtCore.pyqtSignal(object)  # LogEvent
    connection_changed = QtCore.pyqtSignal(bool)
    relay_result_received = QtCore.pyqtSignal(object)

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._started_monotonic = time.monotonic()
        self.latest_values: dict[str, float] = {}
        self.latest_frame: SensorFrame | None = None
        self.connected = False

    @QtCore.pyqtSlot(object)
    def publish_frame(self, frame: SensorFrame) -> None:
        self.latest_frame = frame
        self.latest_values.update(frame.values)
        self.frame_received.emit(frame)

    @QtCore.pyqtSlot(object)
    def publish_log_event(self, event: LogEvent) -> None:
        self.log_received.emit(event)

    @QtCore.pyqtSlot(bool)
    def set_connected(self, connected: bool) -> None:
        self.connected = bool(connected)
        self.connection_changed.emit(self.connected)

    @QtCore.pyqtSlot(object)
    def publish_relay_result(self, result: object) -> None:
        self.relay_result_received.emit(result)

    def log(
        self,
        message: str,
        *,
        level: str = "INFO",
        source: str = "application",
        details: dict[str, Any] | None = None,
    ) -> LogEvent:
        event = LogEvent(
            timestamp_utc=utc_now_iso(),
            elapsed_s=time.monotonic() - self._started_monotonic,
            level=level.upper(),
            source=source,
            message=message,
            details=dict(details or {}),
        )
        self.publish_log_event(event)
        return event
