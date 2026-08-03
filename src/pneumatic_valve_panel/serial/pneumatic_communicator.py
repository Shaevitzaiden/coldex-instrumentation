from __future__ import annotations

"""Templates for integrating multiple real serial devices.

Create one communicator object per device and pass them by key to run_app().
The corresponding communicator_key values live in config/devices.yaml.
"""

from typing import Any
from .serial_interface import SerialCommunicator
import time

class PneumaticCommunicator(SerialCommunicator):
    """Example command-capable microcontroller communicator."""
    def __init__(self):
        super().__init__()
        self.configure_msg_structure('outbound', msg_size=3, start_character='<', end_character='>')

    def connect(
        self,
        *,
        port: str | None = None,
        baudrate: int | None = None,
        timeout_s: float = 0.05,
    ) -> None:
        """Open the serial port. Called inside the controller worker thread."""
        super().connect(port=port, baud_rate=baudrate, timeout=timeout_s, sleep_time=0.01)
    
    def disconnect(self) -> None:
        """Close the serial port during graceful shutdown."""
        super().disconnect()

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


        # This is where the command is built and sent to the device. The format of the command string should match what the device expects.
        cmd = f"{relay_number-1},{int(is_active)}" # Raw unformatted command
        self.write(cmd) # Command is formatted internally
        print(f"Sent command to device: {cmd}")
        print(self.read()) # Read response from device


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


if __name__ == "__main__":
    communicator = PneumaticCommunicator()
    communicator.connect(port="COM3", baudrate=9600, timeout_s=0.5)

    exit_flag = False
    while not exit_flag:
        cmd = input("Enter command (format: relay_number,is_active): ")
        if cmd.lower() in ["exit", "quit", "e", "q"]:
            exit_flag = True
            continue
        else:
            communicator.write(cmd)
            print(communicator.read())




