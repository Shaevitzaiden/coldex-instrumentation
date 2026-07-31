from __future__ import annotations

import math
import time
from typing import Any


class DemoCommunicator:
    """No-hardware communicator with a simulated synchronized sensor stream.

    The hardware worker calls ``read_available_packets`` and receives one
    multi-channel frame. Replace this class with your serial abstraction while
    preserving either this packet format or returning ``SensorFrame`` objects.
    """

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
            raise RuntimeError("Demo communicator is not connected")
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
        return [
            {
                "type": "sensor_frame",
                "sequence": self._sequence,
                "device_timestamp": elapsed,
                "values": {
                    "pressure_supply": 550.0 + 8.0 * math.sin(elapsed * 0.55),
                    "pressure_output": 120.0 + active_relays * 12.0 + 4.0 * math.sin(elapsed * 1.1),
                    "flow_rate": 1.5 + active_relays * 0.22 + 0.1 * math.cos(elapsed * 0.8),
                    "temperature": 27.0 + 0.5 * math.sin(elapsed * 0.08),
                },
            }
        ]
