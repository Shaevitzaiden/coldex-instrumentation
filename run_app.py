"""Launch the dashboard with the configured hardware communicators.

The mapping keys must match ``communicator_key`` values in ``config/devices.yaml``.
Each communicator is owned by its own DeviceWorker/QThread; GUI widgets never
open or poll serial ports directly.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pneumatic_valve_panel.app import run_app
from pneumatic_valve_panel.serial.demo_communicator import DemoEnvironmentalCommunicator
from pneumatic_valve_panel.serial.pneumatic_communicator import PneumaticCommunicator


if __name__ == "__main__":
    raise SystemExit(
        run_app(
            config_path=ROOT / "config" / "valve_panel.yaml",
            dashboard_config_path=ROOT / "config" / "dashboard.yaml",
            sensor_config_path=ROOT / "config" / "sensors.yaml",
            device_config_path=ROOT / "config" / "devices.yaml",
            actuator_config_path=ROOT / "config" / "actuators.yaml",
            data_root=ROOT / "recorded_sessions",
            communicators={
                "controller": PneumaticCommunicator(),
                "environment": DemoEnvironmentalCommunicator(),
            },
        )
    )
