"""Driver for firmware/thermocouple_reader (MCP9601 K-type thermocouple)."""

from __future__ import annotations

from . import register_driver
from .line_sensor import LineSerialSensor

# Integer status codes printed by thermocouple_reader.ino. Temperatures are
# always printed with a decimal point (e.g. "16.00"), so "16" is unambiguous.
STATUS_MESSAGES = {
    15: "MCP9601 not found on I2C (check wiring/address)",
    16: "thermocouple open circuit (probe unplugged or broken)",
    17: "thermocouple short circuit",
    18: "thermocouple conversion not ready",
}


@register_driver("mcp9601_thermocouple")
class Mcp9601Thermocouple(LineSerialSensor):
    """MCP9601 K-type thermocouple reader (firmware/thermocouple_reader)."""

    def __init__(self, channel: str = "temperature", **options) -> None:
        super().__init__(**options)
        self.channel = channel
        self._last_status: int | None = None

    def parse_line(self, line: str):
        if line.isdigit():
            code = int(line)
            if code == self._last_status:
                return None  # repeated status: warn only once
            self._last_status = code
            return f"Thermocouple: {STATUS_MESSAGES.get(code, f'unknown status {code}')}"
        value = float(line)
        self._last_status = None
        return {self.channel: value}
