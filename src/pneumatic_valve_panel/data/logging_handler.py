from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from PyQt5 import QtCore

from .models import LogEvent


class _LogEmitter(QtCore.QObject):
    event = QtCore.pyqtSignal(object)


class DataHubLoggingHandler(logging.Handler):
    """Forward standard-library logging records into the Qt log stream."""

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__()
        self.emitter = _LogEmitter(parent)
        self._started_monotonic = time.monotonic()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            event = LogEvent(
                timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                elapsed_s=time.monotonic() - self._started_monotonic,
                level=record.levelname,
                source=record.name,
                message=message,
                details={
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno,
                },
            )
            self.emitter.event.emit(event)
        except Exception:
            self.handleError(record)
