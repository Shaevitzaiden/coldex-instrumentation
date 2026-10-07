from __future__ import annotations

"""Application entry point and dependency injection boundary."""

import sys
from pathlib import Path
from typing import Any

from PyQt5 import QtWidgets

from .main_window import MainWindow


def run_app(
    config_path: str | Path,
    communicator: Any = None,
    *,
    communicators: dict[str, Any] | None = None,
    dashboard_config_path: str | Path | None = None,
    sensor_config_path: str | Path | None = None,
    device_config_path: str | Path | None = None,
    actuator_config_path: str | Path | None = None,
    data_root: str | Path | None = None,
    demo_mode: bool = False,
) -> int:
    """Create and run the Qt application.

    Devices are normally built from the ``driver:`` entries in devices.yaml
    (see ``pneumatic_valve_panel.drivers``). ``demo_mode=True`` uses each
    device's ``demo_driver`` instead, so the app runs with no hardware.

    Advanced use: ``communicators={"controller": obj}`` injects ready-made
    objects by ``communicator_key`` and takes precedence over ``driver``.
    ``communicator=...`` is still accepted for the command-target device.
    """

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    window = MainWindow(
        config_path=Path(config_path),
        communicator=communicator,
        communicators=communicators,
        dashboard_config_path=Path(dashboard_config_path) if dashboard_config_path else None,
        sensor_config_path=Path(sensor_config_path) if sensor_config_path else None,
        device_config_path=Path(device_config_path) if device_config_path else None,
        actuator_config_path=Path(actuator_config_path) if actuator_config_path else None,
        data_root=Path(data_root) if data_root else None,
        demo_mode=demo_mode,
    )
    window.show()
    return app.exec_()
