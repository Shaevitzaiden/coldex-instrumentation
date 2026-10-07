#!/usr/bin/env python3
"""Small, reusable line-oriented serial transport.

This class deliberately handles only connection lifecycle, framing, and basic
line reads/writes. Device-specific command semantics belong in subclasses such
as :class:`PneumaticCommunicator`.
"""

from __future__ import annotations

import atexit
import time
from typing import Any

import serial
from serial.serialutil import SerialException


class SerialCommunicator:
    """Semi-general serial communicator used by hardware-specific adapters.

    ``outbound_structure`` controls optional start/end markers added to outgoing
    commands. Incoming data is currently treated as newline-delimited text,
    which matches the Arduino relay-controller protocol used by this project.
    """

    def __init__(self, close_port_on_exit: bool = True) -> None:
        self.port: str | None = None
        self.baud_rate: int | None = None
        self.ser: serial.Serial | None = None

        self.outbound_structure: dict[str, Any] = {
            "msg_size": 2,
            "start_character": None,
            "delimiter": None,
            "end_character": None,
            "encoding": "UTF-8",
        }
        self.inbound_structure: dict[str, Any] = {
            "msg_size": 1,
            "start_character": None,
            "delimiter": None,
            "end_character": None,
            "encoding": "UTF-8",
        }

        # Retained for future command-name mappings used by some instruments.
        self.commands: dict[str, Any] = {}

        if close_port_on_exit:
            atexit.register(self.disconnect)

    @property
    def is_connected(self) -> bool:
        """Return True only while a real serial port is open."""
        return bool(self.ser is not None and self.ser.is_open)

    def connect(
        self,
        port: str,
        baud_rate: int,
        timeout: float = 1.0,
        sleep_time: float = 0.01,
    ) -> None:
        """Open ``port`` and raise ``SerialException`` if it cannot be opened.

        Raising the connection error is intentional: ``DeviceWorker`` uses it
        to report an accurate disconnected state instead of falsely publishing
        a successful connection after a failed ``serial.Serial`` call.
        """
        self.disconnect()
        self.port = port
        self.baud_rate = baud_rate

        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=baud_rate,
                timeout=timeout,
                write_timeout=timeout,
            )
            # Many Arduino-class boards reset when the port opens. Keep this
            # delay configurable because some native-USB devices do not need it.
            if sleep_time > 0:
                time.sleep(sleep_time)
            self.ser.reset_input_buffer()
        except SerialException:
            self.ser = None
            raise

    def disconnect(self) -> None:
        """Close the serial connection if it is open."""
        if self.ser is not None:
            try:
                if self.ser.is_open:
                    self.ser.close()
            finally:
                self.ser = None

    def _require_connection(self) -> serial.Serial:
        if not self.is_connected:
            raise ConnectionError("Serial port is not connected")
        assert self.ser is not None
        return self.ser

    def write(self, cmd: Any) -> int:
        """Frame and transmit one command, returning bytes written."""
        ser = self._require_connection()
        payload = self._build_msg(cmd)
        count = ser.write(payload)
        ser.flush()
        return count

    def read(self, timeout: float | None = 1.0) -> str:
        """Read one newline-terminated response.

        ``pyserial.readline``/``read_until`` already implements the timeout we
        need, so there is no separate polling loop. A missing line is reported
        as ``TimeoutError`` rather than an ambiguous empty string.
        """
        ser = self._require_connection()
        previous_timeout = ser.timeout
        if timeout is not None:
            ser.timeout = timeout
        try:
            data = ser.read_until(b"\n")
        finally:
            ser.timeout = previous_timeout

        if not data:
            raise TimeoutError("Timeout waiting for serial data")
        return data.decode(self.inbound_structure["encoding"], errors="replace").strip("\r\n")

    def _build_msg(self, msg: Any) -> bytes:
        """Package a command using the configured outbound framing."""
        pieces: list[str] = []
        if self.outbound_structure["start_character"] is not None:
            pieces.append(str(self.outbound_structure["start_character"]))
        pieces.append(str(msg))
        if self.outbound_structure["end_character"] is not None:
            pieces.append(str(self.outbound_structure["end_character"]))
        return "".join(pieces).encode(self.outbound_structure["encoding"])

    def configure_msg_structure(self, msg_dir: str, **kwargs: Any) -> None:
        """Update inbound or outbound framing settings."""
        if msg_dir not in {"inbound", "outbound"}:
            raise ValueError("msg_dir must be 'inbound' or 'outbound'")
        config_dict = self.inbound_structure if msg_dir == "inbound" else self.outbound_structure
        for key, value in kwargs.items():
            if key not in config_dict:
                raise KeyError(f"Unknown message-structure key: {key}")
            config_dict[key] = value

    def load_msg_structure(self, msg_dir: str) -> None:
        """Reserved for a future YAML-driven framing configuration."""
        raise NotImplementedError("Message-structure loading from YAML is not implemented")


if __name__ == "__main__":
    # Minimal manual smoke test. Adjust COM port before use.
    communicator = SerialCommunicator()
    communicator.configure_msg_structure("outbound", start_character="<", end_character=">")
    try:
        communicator.connect("COM3", 9600, timeout=0.5, sleep_time=0.5)
        communicator.write("0,1")
        print(communicator.read(timeout=2.0))
    finally:
        communicator.disconnect()
