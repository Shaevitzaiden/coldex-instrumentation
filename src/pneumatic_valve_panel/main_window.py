from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PyQt5 import QtCore, QtWidgets

from .config_io import load_panel_config, save_panel_config
from .controllers.valve_controller import ValveController
from .models import PanelConfig
from .serial.protocols import ValveCommunicator
from .widgets.valve_panel import ValvePanel


class MainWindow(QtWidgets.QMainWindow):
    """Small application shell around the reusable ValvePanel widget."""

    def __init__(
        self,
        *,
        config_path: Path,
        communicator: Optional[ValveCommunicator] = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.config_path = Path(config_path)
        self.panel_config: PanelConfig = load_panel_config(self.config_path)
        self.controller = ValveController(
            panel_config=self.panel_config,
            communicator=communicator,
            logger=self.logger,
        )

        self.setWindowTitle(self.panel_config.title)
        self.resize(min(self.panel_config.width + 80, 1400), min(self.panel_config.height + 140, 900))

        self.valve_panel = ValvePanel(panel_config=self.panel_config, controller=self.controller)
        self.valve_panel.message.connect(self.statusBar().showMessage)

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(False)
        scroll_area.setWidget(self.valve_panel)
        self.setCentralWidget(scroll_area)

        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self.statusBar().showMessage(f"Loaded {self.config_path}")

    def set_communicator(self, communicator: ValveCommunicator | None) -> None:
        self.controller.set_communicator(communicator)

    def _create_actions(self) -> None:
        self.load_config_action = QtWidgets.QAction("Load Panel Config...", self)
        self.load_config_action.triggered.connect(self._load_config_dialog)

        self.save_config_action = QtWidgets.QAction("Save Layout", self)
        self.save_config_action.triggered.connect(self._save_layout)
        self.save_config_action.setShortcut("Ctrl+S")

        self.save_config_as_action = QtWidgets.QAction("Save Layout As...", self)
        self.save_config_as_action.triggered.connect(self._save_layout_as)

        self.edit_layout_action = QtWidgets.QAction("Edit Layout", self)
        self.edit_layout_action.setCheckable(True)
        self.edit_layout_action.toggled.connect(self.valve_panel.set_edit_mode)

        self.close_all_action = QtWidgets.QAction("Close All Valves", self)
        self.close_all_action.triggered.connect(self._close_all_valves)

        self.quit_action = QtWidgets.QAction("Quit", self)
        self.quit_action.triggered.connect(self.close)
        self.quit_action.setShortcut("Ctrl+Q")

    def _create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.load_config_action)
        file_menu.addAction(self.save_config_action)
        file_menu.addAction(self.save_config_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)

        valves_menu = self.menuBar().addMenu("Valves")
        valves_menu.addAction(self.close_all_action)
        valves_menu.addAction(self.edit_layout_action)

    def _create_toolbar(self) -> None:
        toolbar = self.addToolBar("Valve Controls")
        toolbar.setMovable(False)
        toolbar.addAction(self.close_all_action)
        toolbar.addSeparator()
        toolbar.addAction(self.edit_layout_action)
        toolbar.addAction(self.save_config_action)

    def _load_config_dialog(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load panel config",
            str(self.config_path.parent),
            "YAML files (*.yaml *.yml);;All files (*)",
        )
        if not path:
            return
        self._load_config(Path(path))

    def _load_config(self, path: Path) -> None:
        config = load_panel_config(path)
        self.config_path = path
        self.panel_config = config
        self.controller.set_panel_config(config)
        self.valve_panel.set_panel_config(config)
        self.setWindowTitle(config.title)
        self.statusBar().showMessage(f"Loaded {path}")

    def _save_layout(self) -> None:
        self.valve_panel.sync_button_positions_to_config()
        save_panel_config(self.panel_config, self.config_path)
        self.statusBar().showMessage(f"Saved {self.config_path}")

    def _save_layout_as(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save panel config as",
            str(self.config_path),
            "YAML files (*.yaml *.yml);;All files (*)",
        )
        if not path:
            return
        self.config_path = Path(path)
        self._save_layout()

    def _close_all_valves(self) -> None:
        try:
            self.valve_panel.set_all_buttons_checked(False, send=True)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Close all failed", str(exc))
            return
        self.statusBar().showMessage("Close-all command sent")

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        if self.edit_layout_action.isChecked():
            response = QtWidgets.QMessageBox.question(
                self,
                "Save layout?",
                "Layout edit mode is enabled. Save current button positions before closing?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel,
            )
            if response == QtWidgets.QMessageBox.Cancel:
                event.ignore()
                return
            if response == QtWidgets.QMessageBox.Yes:
                self._save_layout()
        super().closeEvent(event)
