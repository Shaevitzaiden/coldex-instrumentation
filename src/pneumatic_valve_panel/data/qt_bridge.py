from __future__ import annotations

"""Rate-limited bridge from the non-Qt StreamHub into GUI-safe Qt signals."""

from PyQt5 import QtCore

from .models import CommandResult, DeviceStatus, LogEvent, SensorFrame
from .stream_hub import OverflowPolicy, StreamHub


class QtDataBridge(QtCore.QObject):
    """Drain hub subscriptions on the GUI thread at a controlled rate.

    Serial devices may publish hundreds or thousands of frames per second.  Qt
    widgets should not receive one cross-thread signal per raw sample.  The
    bridge instead drains bounded subscriber queues every few milliseconds.
    Recording and automation bypass this bridge and consume directly from the
    hub at full rate.
    """

    frame_received = QtCore.pyqtSignal(object)
    log_received = QtCore.pyqtSignal(object)
    command_result_received = QtCore.pyqtSignal(object)
    device_status_received = QtCore.pyqtSignal(object)

    def __init__(
        self,
        *,
        stream_hub: StreamHub,
        poll_interval_ms: int = 20,
        max_frames_per_tick: int = 250,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.stream_hub = stream_hub
        self.max_frames_per_tick = max(1, int(max_frames_per_tick))

        self._frame_subscription = stream_hub.subscribe(
            "frames/*",
            queue_size=4000,
            overflow_policy=OverflowPolicy.DROP_OLDEST,
            name="qt-frame-bridge",
        )
        self._event_subscription = stream_hub.subscribe(
            ("logs/*", "commands/results/*", "devices/status/*"),
            queue_size=4000,
            overflow_policy=OverflowPolicy.DROP_OLDEST,
            name="qt-event-bridge",
        )

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._drain)
        self._timer.start(max(5, int(poll_interval_ms)))

    @QtCore.pyqtSlot()
    def _drain(self) -> None:
        for envelope in self._frame_subscription.drain(self.max_frames_per_tick):
            if isinstance(envelope.payload, SensorFrame):
                self.frame_received.emit(envelope.payload)

        for envelope in self._event_subscription.drain(self.max_frames_per_tick):
            payload = envelope.payload
            if isinstance(payload, LogEvent):
                self.log_received.emit(payload)
            elif isinstance(payload, DeviceStatus):
                self.device_status_received.emit(payload)
            elif isinstance(payload, (CommandResult, dict)):
                self.command_result_received.emit(payload)

    def close(self) -> None:
        self._timer.stop()
        self._frame_subscription.close()
        self._event_subscription.close()
