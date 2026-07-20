from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from PyQt5 import QtWidgets

from .main_window import MainWindow


def run_app(config_path: str | Path, communicator: Any = None) -> int:
    """Create and run the Qt application.

    ``communicator`` is user-provided. The GUI will call either
    ``set_element_state(...)`` or the older ``set_valve_state(...)`` if present.
    """

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    window = MainWindow(config_path=Path(config_path), communicator=communicator)
    window.show()
    return app.exec_()
