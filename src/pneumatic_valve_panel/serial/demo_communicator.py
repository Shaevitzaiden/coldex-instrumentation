from __future__ import annotations

"""Simulated communicators demonstrating independent multi-device streams."""

import math
import time
from typing import Any


class DemoCommunicator:
    """Controller MCU simulation: relay commands plus synchronized telemetry."""

    def __init__(self) -> None:
        self._connected = False
        self._started = time.monotonic()
        self._last_frame = 0.0
        self._relay_states: dict[int, bool] = {}
        self._sequence = 0

    def connect(self) -> None:
        self._connected = True
        self._started = time.monotonic()

    def disconnect(self) -> None:
        self._connected = False

    def set_element_state(
        self,
        *,
        element_id: str,
        element_type: str,
        is_active: bool,
        relay_number: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self._connected:
            raise RuntimeError("Demo controller is not connected")
        if relay_number is not None:
            self._relay_states[int(relay_number)] = bool(is_active)

    def set_valve_state(
        self,
        *,
        valve_id: str,
        is_open: bool,
        command_id: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.set_element_state(
            element_id=valve_id,
            element_type=str((metadata or {}).get("element_type", "unknown")),
            is_active=is_open,
            relay_number=int(command_id) if command_id is not None else None,
            metadata=metadata,
        )

    def read_available_packets(self, timeout_s: float = 0.01) -> list[dict[str, Any]]:
        if not self._connected:
            time.sleep(min(timeout_s, 0.01))
            return []
        now = time.monotonic()
        if now - self._last_frame < 0.05:
            time.sleep(min(timeout_s, 0.005))
            return []
        self._last_frame = now
        elapsed = now - self._started
        self._sequence += 1
        active_relays = sum(self._relay_states.values())
        # Local channel names are mapped to global IDs by DeviceWorker using the
        # source_device/source_channel entries in sensors.yaml.
        return [
            {
                "type": "sensor_frame",
                "sequence": self._sequence,
                "device_timestamp": elapsed,
                "values": {
                    "pressure_supply": 550.0 + 8.0 * math.sin(elapsed * 0.55),
                    "pressure_output": 120.0 + active_relays * 12.0 + 4.0 * math.sin(elapsed * 1.1),
                    "flow_rate": 1.5 + active_relays * 0.22 + 0.1 * math.cos(elapsed * 0.8),
                    "controller_temperature": 27.0 + 0.5 * math.sin(elapsed * 0.08),
                },
            }
        ]


class DemoEnvironmentalCommunicator:
    """Second serial-device simulation with its own rate and clock."""

    def __init__(self) -> None:
        self._connected = False
        self._started = time.monotonic()
        self._last_frame = 0.0
        self._sequence = 0

    def connect(self) -> None:
        self._connected = True
        self._started = time.monotonic()

    def disconnect(self) -> None:
        self._connected = False

    def read_available_packets(self, timeout_s: float = 0.01) -> list[dict[str, Any]]:
        if not self._connected:
            time.sleep(min(timeout_s, 0.01))
            return []
        now = time.monotonic()
        if now - self._last_frame < 0.2:  # independent 5 Hz instrument
            time.sleep(min(timeout_s, 0.01))
            return []
        self._last_frame = now
        elapsed = now - self._started
        self._sequence += 1
        return [
            {
                "type": "sensor_frame",
                "sequence": self._sequence,
                "device_timestamp": elapsed,
                "values": {
                    "ambient_temperature": 22.0 + 0.8 * math.sin(elapsed * 0.03),
                    "relative_humidity": 42.0 + 2.0 * math.cos(elapsed * 0.02),
                },
            }
        ]
