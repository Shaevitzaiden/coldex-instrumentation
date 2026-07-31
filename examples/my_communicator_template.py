from __future__ import annotations

"""Templates for integrating multiple real serial devices.

Create one communicator object per device and pass them by key to run_app().
The corresponding communicator_key values live in config/devices.yaml.
"""

from typing import Any


class ControllerCommunicator:
    """Example command-capable microcontroller communicator."""

    def connect(
        self,
        *,
        port: str | None = None,
        baudrate: int | None = None,
        timeout_s: float = 0.05,
    ) -> None:
        """Open the serial port. Called inside the controller worker thread."""
        # self.protocol.open(port=port, baudrate=baudrate, timeout=timeout_s)

    def disconnect(self) -> None:
        """Close the serial port during graceful shutdown."""
        # self.protocol.close()

    def set_element_state(
        self,
        *,
        element_id: str,
        element_type: str,
        is_active: bool,
        relay_number: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if relay_number is None:
            raise ValueError(f"{element_id} has no relay binding")
        # self.protocol.set_relay(relay_number, is_active)

    def read_available_packets(self, timeout_s: float = 0.01) -> list[dict[str, Any]]:
        """Return parsed packets with local channel names.

        All simultaneously sampled channels should be returned in one values
        mapping so they retain an identical synchronized timestamp.
        """
        # packet = self.protocol.read_packet(timeout_s)
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


class FlowMeterCommunicator:
    """Example second, telemetry-only serial device."""

    def connect(self, *, port: str | None = None, baudrate: int | None = None, **_: Any) -> None:
        # self.meter.open(port, baudrate)
        pass

    def disconnect(self) -> None:
        # self.meter.close()
        pass

    def read_available_packets(self, timeout_s: float = 0.01) -> list[dict[str, Any]]:
        # value = self.meter.read_flow(timeout_s)
        # return [] if value is None else [{"type": "sensor_frame", "values": {"flow": value}}]
        return []


# Application injection example:
#
# run_app(
#     config_path="config/valve_panel.yaml",
#     device_config_path="config/devices.yaml",
#     communicators={
#         "controller": ControllerCommunicator(),
#         "flow_meter": FlowMeterCommunicator(),
#     },
# )
