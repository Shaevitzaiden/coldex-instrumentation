"""Template showing how to connect your serial layer to the GUI.

Copy this idea into run_app.py once your communicator is ready.
"""
from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pneumatic_valve_panel.app import run_app


class MySerialCommunicator:
    """Replace this with your real firmware/software serial abstraction."""

    def __init__(self) -> None:
        # Example only:
        # self.device = MyDevice(port="COM4", baudrate=115200)
        # self.device.connect()
        pass

    def set_valve_state(
        self,
        *,
        valve_id: str,
        is_open: bool,
        command_id: Any = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        """Called whenever a valve button is toggled.

        Parameters
        ----------
        valve_id:
            Stable GUI/config id, such as "valve_01".
        is_open:
            True when the GUI requests open/on; False for closed/off.
        command_id:
            Optional value from YAML. In the included example config this is the
            legacy Arduino digital pin, but you can replace it with your own
            channel id or structured command.
        metadata:
            Extra YAML-defined data for this valve.
        """
        metadata = metadata or {}
        print(
            "Send serial command here:",
            {"valve_id": valve_id, "is_open": is_open, "command_id": command_id, "metadata": metadata},
        )
        # Example only:
        # self.device.set_channel(command_id, state=is_open)


if __name__ == "__main__":
    run_app(
        config_path=ROOT / "config" / "valve_panel.yaml",
        communicator=MySerialCommunicator(),
    )
