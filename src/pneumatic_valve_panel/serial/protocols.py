from __future__ import annotations

"""Structural interfaces for injected device communicators.

These Protocols are optional type-checking aids.  A communicator does not need
to inherit from them; it only needs to provide compatible methods.
"""

from typing import Any, Protocol


class PneumaticCommunicator(Protocol):
    """Command interface for the device that owns pneumatic relays."""

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


class StreamingCommunicator(Protocol):
    """Full-duplex interface owned by one DeviceWorker.

    Each communicator represents exactly one independently managed device.  It
    may be command-capable, telemetry-only, or both.  ``read_available_packets``
    should return local channel names; DeviceWorker maps them to globally
    qualified IDs using sensors.yaml.
    """

    def connect(self, **connection: Any) -> None:
        ...

    def disconnect(self) -> None:
        ...

    def read_available_packets(self, timeout_s: float = 0.01) -> list[dict[str, Any]]:
        """Return zero or more parsed packets.

        Preferred synchronized frame format::

            {
                "type": "sensor_frame",
                "sequence": 42,
                "device_timestamp": 12.345,
                "values": {
                    "pressure_supply": 101.2,
                    "flow_rate": 3.4,
                },
            }

        Every channel in ``values`` keeps one shared host/device timestamp.
        """
        ...


class GenericCommandCommunicator(Protocol):
    """Optional extension point for non-pneumatic instrument commands."""

    def execute_command(self, command: Any) -> Any:
        ...


class ValveCommunicator(Protocol):
    """Backwards-compatible command API from the earliest panel version."""

    def set_valve_state(
        self,
        *,
        valve_id: str,
        is_open: bool,
        command_id: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        ...
