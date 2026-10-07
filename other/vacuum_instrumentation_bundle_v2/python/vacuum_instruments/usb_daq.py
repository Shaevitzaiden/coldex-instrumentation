"""Host driver for the Feather RP2040 Adalogger JSON-over-USB protocol."""

from __future__ import annotations

import json
import time
from typing import Any, Iterator

import serial


class AdaloggerDAQ:
    """Blocking host driver shared by native-ADC and ADS1115 firmware variants.

    Firmware emits newline-delimited JSON. Commands such as ``READ`` or ``INFO``
    receive one JSON reply; ``START`` enables asynchronous ``sample`` records.
    """

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 1.0):
        self.ser = serial.Serial(
            port,
            baudrate=baudrate,
            timeout=timeout,
            write_timeout=timeout,
        )
        # Native USB boards can take a moment to enumerate/reset after opening.
        time.sleep(0.5)
        self.ser.reset_input_buffer()

    def close(self) -> None:
        if self.ser.is_open:
            self.ser.close()

    def __enter__(self) -> "AdaloggerDAQ":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _decode_json_line(line: bytes) -> dict[str, Any]:
        try:
            obj = json.loads(line.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Malformed DAQ JSON line: {line!r}") from exc
        if not isinstance(obj, dict):
            raise ValueError(f"DAQ message must be a JSON object: {obj!r}")
        return obj

    def command(self, text: str) -> dict[str, Any]:
        """Send one command and return its first relevant JSON response."""
        self.ser.write((text.strip() + "\n").encode("ascii"))
        self.ser.flush()

        timeout = self.ser.timeout if self.ser.timeout is not None else 1.0
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self.ser.readline()
            if not line:
                continue
            obj = self._decode_json_line(line)
            if obj.get("type") in {"ack", "info", "sample", "error"}:
                return obj
        raise TimeoutError(f"DAQ command timed out: {text}")

    def read_once(self) -> dict[str, Any]:
        return self.command("READ")

    def set_rate(self, hz: float) -> dict[str, Any]:
        return self.command(f"RATE {hz}")

    def start(self) -> dict[str, Any]:
        return self.command("START")

    def stop(self) -> dict[str, Any]:
        return self.command("STOP")

    def iter_samples(self) -> Iterator[dict[str, Any]]:
        """Yield asynchronous sample records until the caller stops iteration."""
        while True:
            line = self.ser.readline()
            if not line:
                continue
            obj = self._decode_json_line(line)
            if obj.get("type") == "sample":
                yield obj
