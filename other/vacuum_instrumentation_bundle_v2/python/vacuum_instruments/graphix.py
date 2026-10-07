"""Leybold GRAPHIX RS-232 protocol helper.

The GRAPHIX protocol is an ASCII request/response protocol framed by control
bytes. This module intentionally keeps protocol handling independent from the
main PyQt application so it can be smoke-tested on the bench first.

When integrating into the main application, wrap this class in a communicator
that implements the DeviceWorker telemetry contract documented in
``src/pneumatic_valve_panel/README.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

import serial


class GraphixError(RuntimeError):
    """Base exception for malformed/failed GRAPHIX transactions."""


class GraphixNack(GraphixError):
    """Raised when the controller explicitly returns NACK."""


@dataclass(frozen=True)
class GraphixPressure:
    channel: int
    value: float
    unit: str
    raw: str


class GraphixController:
    """Minimal blocking driver for one GRAPHIX controller."""

    SI = 0x0F
    SO = 0x0E
    ACK = 0x06
    NACK = 0x15
    EOT = 0x04

    def __init__(self, port: str, baudrate: int = 38400, timeout: float = 0.5):
        self.ser = serial.Serial(
            port,
            baudrate=baudrate,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=timeout,
            write_timeout=timeout,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

    def close(self) -> None:
        if self.ser and self.ser.is_open:
            self.ser.close()

    def __enter__(self) -> "GraphixController":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def checksum(data: bytes) -> int:
        """Return the one-byte checksum defined by the GRAPHIX manual."""
        checksum = 255 - (sum(data) % 256)
        return checksum + 32 if checksum < 32 else checksum

    @classmethod
    def make_read_frame(cls, group: int, parameter: int) -> bytes:
        """Build ``SI + 'group;parameter' + checksum + EOT``."""
        body = bytes([cls.SI]) + f"{group};{parameter}".encode("ascii")
        return body + bytes([cls.checksum(body), cls.EOT])

    def _read_frame(self) -> bytes:
        data = self.ser.read_until(bytes([self.EOT]))
        if not data:
            raise TimeoutError("GRAPHIX did not respond")
        if data[-1] != self.EOT:
            raise GraphixError(f"Incomplete response: {data!r}")
        if len(data) < 3:
            raise GraphixError(f"Response too short: {data!r}")

        expected = self.checksum(data[:-2])
        received = data[-2]
        if expected != received:
            raise GraphixError(
                f"Checksum mismatch expected={expected} received={received}: {data!r}"
            )
        return data

    def read_parameter(self, group: int, parameter: int) -> str:
        """Read one GRAPHIX parameter and return its ASCII payload."""
        self.ser.reset_input_buffer()
        self.ser.write(self.make_read_frame(group, parameter))
        self.ser.flush()

        response = self._read_frame()
        kind = response[0]
        text = response[1:-2].decode("ascii", errors="replace").strip()

        if kind == self.NACK:
            raise GraphixNack(text)
        if kind != self.ACK:
            raise GraphixError(
                f"Unexpected response byte 0x{kind:02X}: {response!r}"
            )
        return text

    def identify(self) -> str:
        """Return the controller hardware/software identification parameter."""
        return self.read_parameter(5, 1)

    def read_pressure(self, channel: int = 1) -> GraphixPressure:
        """Read corrected pressure (parameter 29) from gauge channel 1..3."""
        if channel not in (1, 2, 3):
            raise ValueError("channel must be 1, 2, or 3")

        raw = self.read_parameter(channel, 29)
        match = re.match(
            r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?)\s*(.*)$",
            raw,
        )
        if not match:
            raise GraphixError(f"Cannot parse pressure response {raw!r}")
        return GraphixPressure(
            channel=channel,
            value=float(match.group(1)),
            unit=match.group(2).strip(),
            raw=raw,
        )
