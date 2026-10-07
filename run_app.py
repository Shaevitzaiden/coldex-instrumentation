"""Start the pneumatic control dashboard.

    python run_app.py                 # real hardware, as configured in config/devices.yaml
    python run_app.py --demo          # no hardware: every device is simulated
    python run_app.py --list-drivers  # show the instrument drivers that are installed

Which hardware is used, and on which COM port, is set in config/devices.yaml.
New instruments are added as driver files in src/pneumatic_valve_panel/drivers/
(see docs/ADDING_A_DEVICE.md); this file does not need to change.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> int:
    parser = argparse.ArgumentParser(description="Pneumatic control & instrumentation dashboard")
    parser.add_argument("--demo", action="store_true", help="simulate every device (no hardware needed)")
    parser.add_argument("--list-drivers", action="store_true", help="list installed device drivers and exit")
    parser.add_argument("--config-dir", type=Path, default=ROOT / "config", help="folder holding the YAML files")
    args = parser.parse_args()

    if args.list_drivers:
        from pneumatic_valve_panel.drivers import available_drivers, driver_load_errors

        for name, description in available_drivers().items():
            print(f"  {name:<24} {description}")
        for module, error in driver_load_errors().items():
            print(f"  !! {module}.py failed to load: {error}")
        return 0

    from pneumatic_valve_panel.app import run_app

    config = args.config_dir
    return run_app(
        config_path=config / "valve_panel.yaml",
        dashboard_config_path=config / "dashboard.yaml",
        sensor_config_path=config / "sensors.yaml",
        device_config_path=config / "devices.yaml",
        actuator_config_path=config / "actuators.yaml",
        data_root=ROOT / "recorded_sessions",
        demo_mode=args.demo,
    )


if __name__ == "__main__":
    raise SystemExit(main())
