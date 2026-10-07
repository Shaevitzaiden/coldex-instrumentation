from __future__ import annotations

"""Base class for instruments that print one reading per line of text.

Most simple Arduino sensors work this way: ``Serial.println(value)``. To support
one, subclass :class:`LineSerialSensor` and write a single method,
``parse_line``, that turns one line of text into ``{"channel": value}``.
The base class handles the serial port, partial lines and timing.
"""

from typing import Any

import serial


class LineSerialSensor:
    """Serial instrument that sends newline-terminated text readings."""

    #: Lines starting with this prefix are treated as comments and skipped.
    comment_prefix = "#"

    def __init__(self, **options: Any) -> None:
        self.options = options
        self._serial: serial.Serial | None = None
        self._buffer = b""

    @property
    def is_connected(self) -> bool:
        return bool(self._serial is not None and self._serial.is_open)

    def connect(self, port: str | None = None, baudrate: int = 9600, timeout_s: float = 0.05, **_: Any) -> None:
        if not port:
            raise ValueError(f"{type(self).__name__}: devices.yaml needs connection.port")
        self.disconnect()
        self._serial = serial.Serial(port=port, baudrate=baudrate, timeout=timeout_s)
        self._serial.reset_input_buffer()
        self._buffer = b""

    def disconnect(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            finally:
                self._serial = None

    def read_available_packets(self, timeout_s: float = 0.01) -> list[dict[str, Any]]:
        del timeout_s
        if self._serial is None:
            raise ConnectionError("Serial port is not open")
        waiting = self._serial.in_waiting
        if waiting:
            self._buffer += self._serial.read(waiting)
        packets: list[dict[str, Any]] = []
        while b"\n" in self._buffer:
            raw, self._buffer = self._buffer.split(b"\n", 1)
            line = raw.decode("utf-8", errors="replace").strip()
            if not line or line.startswith(self.comment_prefix):
                continue
            try:
                result = self.parse_line(line)
            except ValueError:
                packets.append({
                    "type": "log",
                    "level": "WARNING",
                    "message": f"{type(self).__name__}: could not understand line {line!r}",
                })
                continue
            if isinstance(result, dict) and result:
                packets.append({"type": "sensor_frame", "values": result})
            elif isinstance(result, str) and result:
                packets.append({"type": "log", "level": "WARNING", "message": result})
        return packets

    def parse_line(self, line: str) -> dict[str, float] | str | None:
        """Turn one line into ``{"channel_name": value}``.

        Return ``None`` to ignore the line, or a string to show it as a
        warning in the log. Raise ``ValueError`` if the line is garbage.
        """
        raise NotImplementedError
