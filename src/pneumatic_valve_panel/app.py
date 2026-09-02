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
) -> int:
    """Create and run the Qt application.

    Preferred multi-device usage::

        run_app(
            config_path="config/valve_panel.yaml",
            device_config_path="config/devices.yaml",
            communicators={
                "controller": ControllerCommunicator(...),
                "flow_meter": FlowMeterCommunicator(...),
            },
        )

    ``communicator=...`` remains supported and is assigned to the configured
    command-target device for backwards compatibility.
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
    )
    window.show()
    return app.exec_()
