"""Example integration point for your own serial abstraction.

This file is not imported by the GUI. It is meant as a pattern for integrating
whatever serial communicator you have already written.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pneumatic_valve_panel.app import run_app


class MySerialCommunicator:
    def __init__(self) -> None:
        # self.device = YourSerialDevice(...)
        pass

    def set_element_state(
        self,
        *,
        element_id: str,
        element_type: str,
        is_active: bool,
        relay_number: int | None = None,
        metadata: dict | None = None,
    ) -> None:
        if relay_number is None:
            raise ValueError(f"{element_id} is missing a relay binding")

        # Replace this with your new packet abstraction.
        # Example:
        # packet = RelayPacket(relay=relay_number, enabled=is_active)
        # self.device.send(packet)
        print(
            f"Would send: element={element_id}, type={element_type}, "
            f"relay={relay_number}, active={is_active}, metadata={metadata or {}}"
        )


if __name__ == "__main__":
    raise SystemExit(
        run_app(
            config_path=ROOT / "config" / "valve_panel.yaml",
            communicator=MySerialCommunicator(),
        )
    )
