from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

from fake_relay_firmware import FakeRelayFirmware  # noqa: E402


@pytest.fixture
def fake_due(monkeypatch):
    """Patch serial.Serial so PneumaticCommunicator talks to FakeRelayFirmware."""

    from pneumatic_valve_panel.serial import serial_interface

    device = FakeRelayFirmware()

    def open_port(**kwargs):
        device.is_open = True
        device.timeout = kwargs.get("timeout", device.timeout)
        return device

    monkeypatch.setattr(serial_interface.serial, "Serial", open_port)
    return device
