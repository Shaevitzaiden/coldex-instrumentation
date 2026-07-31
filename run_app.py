"""Launch the dashboard with two simulated independent devices.

Replace either demo communicator with your real serial abstraction.  Each object
is owned by a separate device worker/thread according to ``config/devices.yaml``.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pneumatic_valve_panel.app import run_app
from pneumatic_valve_panel.serial.demo_communicator import (
    DemoCommunicator,
    DemoEnvironmentalCommunicator,
)


if __name__ == "__main__":
    raise SystemExit(
        run_app(
            config_path=ROOT / "config" / "valve_panel.yaml",
            dashboard_config_path=ROOT / "config" / "dashboard.yaml",
            sensor_config_path=ROOT / "config" / "sensors.yaml",
            device_config_path=ROOT / "config" / "devices.yaml",
            data_root=ROOT / "recorded_sessions",
            communicators={
                "controller": DemoCommunicator(),
                "environment": DemoEnvironmentalCommunicator(),
            },
        )
    )
