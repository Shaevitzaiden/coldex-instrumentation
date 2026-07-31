from __future__ import annotations

"""Standard-library logging adapter for StreamHub."""

import logging
import time
from datetime import datetime, timezone

from .models import LogEvent
from .stream_hub import StreamHub


class DataHubLoggingHandler(logging.Handler):
    """Forward normal Python logging records into the central stream hub.

    The historical class name is retained so existing imports do not break.
    Unlike earlier versions, no Qt signal is involved; this handler may safely
    be called from any producer thread.
    """

    def __init__(self, stream_hub: StreamHub) -> None:
        super().__init__()
        self.stream_hub = stream_hub
        self._started_monotonic = time.monotonic()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            event = LogEvent(
                timestamp_utc=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                elapsed_s=time.monotonic() - self._started_monotonic,
                level=record.levelname,
                source=record.name,
                message=self.format(record),
                details={
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno,
                },
            )
            self.stream_hub.publish_log(event)
        except Exception:
            self.handleError(record)
