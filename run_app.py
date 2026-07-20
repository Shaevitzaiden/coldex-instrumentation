from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pneumatic_valve_panel.app import run_app
from pneumatic_valve_panel.serial.demo_communicator import DemoCommunicator


if __name__ == "__main__":
    raise SystemExit(
        run_app(
            config_path=ROOT / "config" / "valve_panel.yaml",
            communicator=DemoCommunicator(),
        )
    )
