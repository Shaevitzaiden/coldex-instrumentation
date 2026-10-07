"""TEMPLATE -- copy this file to start a new instrument driver.

This file starts with "_" so it is NOT loaded. After copying it to a name
like ``my_gauge.py`` (no leading underscore), it will be loaded automatically.

There are two kinds of driver. Pick the one that matches your instrument and
delete the other.

A) The instrument prints one reading per line (most Arduino sensors).
   Subclass LineSerialSensor and write parse_line(). See
   mcp9601_thermocouple.py for a complete, real example.

B) The instrument needs to be asked for each reading (most lab controllers,
   e.g. "send PR1, get back a pressure"). Write connect(), disconnect() and
   read_available_packets() yourself, as in ExamplePolledGauge below.

Then add the device to config/devices.yaml and its channels to
config/sensors.yaml. Each channel name you return (e.g. "pressure") becomes
the sensor ID "<device id>.pressure" unless sensors.yaml maps it.
"""

from __future__ import annotations

import time
from typing import Any

import serial

from . import register_driver
from .line_sensor import LineSerialSensor


# ---------------------------------------------------------------------------
# Kind A: one reading per line
# ---------------------------------------------------------------------------
@register_driver("example_line_sensor")
class ExampleLineSensor(LineSerialSensor):
    """Example: an Arduino that prints lines like 'P=101.3,T=22.5'."""

    def parse_line(self, line: str):
        values = {}
        for part in line.split(","):
            name, text = part.split("=", 1)       # "P=101.3" -> "P", "101.3"
            values[name.strip().lower()] = float(text)
        return values                              # {"p": 101.3, "t": 22.5}


# ---------------------------------------------------------------------------
# Kind B: ask for each reading
# ---------------------------------------------------------------------------
@register_driver("example_polled_gauge")
class ExamplePolledGauge:
    """Example: a gauge that answers 'READ?' with a number."""

    def __init__(self, poll_interval_s: float = 1.0) -> None:
        # Values under "options:" in devices.yaml arrive here as arguments.
        self.poll_interval_s = poll_interval_s
        self._serial: serial.Serial | None = None
        self._next_poll = 0.0

    def connect(self, port: str | None = None, baudrate: int = 9600, timeout_s: float = 0.5) -> None:
        # Values under "connection:" in devices.yaml arrive here.
        # Raise an exception if the instrument is not there; the app will show
        # the message and retry every reconnect_interval_s seconds.
        self._serial = serial.Serial(port=port, baudrate=baudrate, timeout=timeout_s)

    def disconnect(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def read_available_packets(self, timeout_s: float = 0.01) -> list[dict[str, Any]]:
        # Called in a loop many times per second. Return [] when there is
        # nothing new; never block for long.
        now = time.monotonic()
        if now < self._next_poll:
            return []
        self._next_poll = now + self.poll_interval_s

        self._serial.write(b"READ?\r\n")
        reply = self._serial.readline().decode().strip()
        if not reply:
            # Raising TimeoutError logs a warning; raising ConnectionError makes
            # the app disconnect and reconnect.
            raise TimeoutError("Gauge did not answer READ?")
        return [{"type": "sensor_frame", "values": {"pressure": float(reply)}}]

    # Optional: accept commands from the GUI by adding
    #   def execute_command(self, command): ...
    # where command.command_type and command.payload describe the request.
