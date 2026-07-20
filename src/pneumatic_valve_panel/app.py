from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PyQt5 import QtWidgets

from .main_window import MainWindow
from .serial.protocols import ValveCommunicator


def run_app(
    config_path: str | Path,
    communicator: Optional[ValveCommunicator] = None,
) -> int:
    """Create and run the Qt application.

    Parameters
    ----------
    config_path:
        YAML file describing the valve panel layout.
    communicator:
        Object that implements ``set_valve_state(...)``. If omitted, the GUI
        still launches, but valve actions are logged as controller warnings.
    """
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    window = MainWindow(config_path=Path(config_path), communicator=communicator)
    window.show()
    return app.exec_()
