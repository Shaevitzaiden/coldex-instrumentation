from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from PyQt5 import QtWidgets

from .main_window import MainWindow


def run_app(
    config_path: str | Path,
    communicator: Any = None,
    *,
    dashboard_config_path: str | Path | None = None,
    sensor_config_path: str | Path | None = None,
    data_root: str | Path | None = None,
) -> int:
    """Create and run the Qt application.

    The injected communicator is owned exclusively by ``HardwareService``. It
    may implement ``connect/disconnect``, element-state commands, and an optional
    non-blocking/polling packet reader such as ``read_available_packets``.
    """

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    window = MainWindow(
        config_path=Path(config_path),
        communicator=communicator,
        dashboard_config_path=Path(dashboard_config_path) if dashboard_config_path else None,
        sensor_config_path=Path(sensor_config_path) if sensor_config_path else None,
        data_root=Path(data_root) if data_root else None,
    )
    window.show()
    return app.exec_()
