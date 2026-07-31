from __future__ import annotations

from typing import Any, Protocol


class PneumaticCommunicator(Protocol):
    """Preferred command side of the injected hardware communicator."""

    def set_element_state(
        self,
        *,
        element_id: str,
        element_type: str,
        is_active: bool,
        relay_number: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        ...


class StreamingCommunicator(PneumaticCommunicator, Protocol):
    """Optional full-duplex interface consumed by ``HardwareService``.

    ``read_available_packets`` should return zero or more dictionaries. The most
    useful packet form is a synchronized multi-channel frame::

        {
            "type": "sensor_frame",
            "sequence": 42,
            "device_timestamp": 12.345,
            "values": {"pressure": 101.2, "flow": 3.4},
        }

    All values in that mapping receive one shared host timestamp.
    """

    def connect(self) -> None:
        ...

    def disconnect(self) -> None:
        ...

    def read_available_packets(self, timeout_s: float = 0.01) -> list[dict[str, Any]]:
        ...


class ValveCommunicator(Protocol):
    """Backwards-compatible command API."""

    def set_valve_state(
        self,
        *,
        valve_id: str,
        is_open: bool,
        command_id: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        ...
