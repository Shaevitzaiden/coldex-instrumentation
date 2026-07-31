from __future__ import annotations

from typing import Any


class MyCommunicator:
    """Template for integrating an existing full-duplex serial abstraction."""

    def connect(self) -> None:
        """Open/configure the serial device. Called in the hardware thread."""
        pass

    def disconnect(self) -> None:
        """Close the serial device. Called during graceful shutdown."""
        pass

    def set_element_state(
        self,
        *,
        element_id: str,
        element_type: str,
        is_active: bool,
        relay_number: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Format and send your relay command here."""
        if relay_number is None:
            raise ValueError(f"{element_id} has no relay binding")
        # self.serial_protocol.set_relay(relay_number, is_active)

    def read_available_packets(self, timeout_s: float = 0.01) -> list[dict[str, Any]]:
        """Return all currently available parsed incoming messages.

        Prefer one dictionary containing all simultaneously sampled channels so
        the application writes the same timestamp to every channel file.
        """
        # packet = self.serial_protocol.read_packet(timeout_s)
        # if packet is None:
        #     return []
        # return [{
        #     "type": "sensor_frame",
        #     "sequence": packet.sequence,
        #     "device_timestamp": packet.timestamp,
        #     "values": {
        #         "pressure_supply": packet.pressure_supply,
        #         "flow_rate": packet.flow_rate,
        #     },
        # }]
        return []
