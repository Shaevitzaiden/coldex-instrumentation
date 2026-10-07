from __future__ import annotations

import pytest

from pneumatic_valve_panel.drivers import available_drivers, create_driver
from pneumatic_valve_panel.drivers.mcp9601_thermocouple import Mcp9601Thermocouple


def test_builtin_drivers_are_registered():
    names = available_drivers()
    for expected in ("relay_controller", "demo_controller", "demo_environment", "mcp9601_thermocouple"):
        assert expected in names


def test_template_is_not_loaded():
    assert "example_line_sensor" not in available_drivers()


def test_unknown_driver_lists_alternatives():
    with pytest.raises(KeyError, match="relay_controller"):
        create_driver("graphix_typo")


def test_options_are_passed_to_driver():
    driver = create_driver("relay_controller", {"status_poll_interval_s": 2.5})
    assert driver.status_poll_interval_s == 2.5


def test_bad_option_names_the_driver():
    with pytest.raises(TypeError, match="relay_controller"):
        create_driver("relay_controller", {"no_such_option": 1})


class _FakePort:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self.is_open = True

    @property
    def in_waiting(self) -> int:
        return len(self._data)

    def read(self, count: int) -> bytes:
        chunk, self._data = self._data[:count], self._data[count:]
        return chunk


def test_thermocouple_parses_temperatures_and_status():
    sensor = Mcp9601Thermocouple()
    sensor._serial = _FakePort(b"# MCP9601 ID/revision: 0x41\n23.50\n16\n16\n24.0")
    packets = sensor.read_available_packets()
    assert packets[0] == {"type": "sensor_frame", "values": {"temperature": 23.5}}
    assert packets[1]["type"] == "log" and "open circuit" in packets[1]["message"]
    assert len(packets) == 2  # repeated status suppressed, partial line kept

    sensor._serial._data = b"\n"
    assert sensor.read_available_packets()[0]["values"]["temperature"] == 24.0
