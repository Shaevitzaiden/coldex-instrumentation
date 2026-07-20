from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PyQt5 import QtCore, QtWidgets

from .config_io import load_panel_config, save_panel_config
from .controllers.pneumatic_controller import PneumaticController
from .models import PanelConfig
from .widgets import ElementDialog, PipeDialog, PropertiesPanel, ValidationPanel, ValvePanelCanvas


class MainWindow(QtWidgets.QMainWindow):
    """Application shell around the reusable scalable valve-panel canvas."""

    def __init__(
        self,
        *,
        config_path: Path,
        communicator: Any = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.config_path = Path(config_path)
        self.panel_config: PanelConfig = load_panel_config(self.config_path)
        self._dirty = False

        self.controller = PneumaticController(
            panel_config=self.panel_config,
            communicator=communicator,
            logger=self.logger,
        )

        self.setWindowTitle(self.panel_config.title)
        self.resize(1400, 800)

        self.canvas = ValvePanelCanvas(panel_config=self.panel_config, controller=self.controller)
        self.canvas.message.connect(self.statusBar().showMessage)
        self.canvas.pipe_mode_changed.connect(self._on_pipe_mode_changed)
        self.canvas.edit_requested.connect(self._on_canvas_edit_requested)
        self.canvas.layout_changed.connect(self._on_layout_changed)
        self.canvas.selection_items_changed.connect(self._on_selection_items_changed)
        self.canvas.history_changed.connect(self._on_history_changed)
        self.setCentralWidget(self.canvas)

        self.properties_panel = PropertiesPanel()
        self.properties_panel.set_panel_config(self.panel_config)
        self.properties_panel.element_changed.connect(self.canvas.update_element)
        self.properties_panel.pipe_changed.connect(self.canvas.update_pipe)
        self.properties_panel.delete_requested.connect(self.canvas.delete_selected)
        self.properties_panel.rotate_requested.connect(self.canvas.rotate_selected)

        self.validation_panel = ValidationPanel(relay_count=24)
        self.validation_panel.set_panel_config(self.panel_config)

        self.properties_dock = QtWidgets.QDockWidget("Properties", self)
        self.properties_dock.setObjectName("PropertiesDock")
        self.properties_dock.setWidget(self.properties_panel)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.properties_dock)

        self.validation_dock = QtWidgets.QDockWidget("Validation / Relay Browser", self)
        self.validation_dock.setObjectName("ValidationDock")
        self.validation_dock.setWidget(self.validation_panel)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.validation_dock)
        self.tabifyDockWidget(self.properties_dock, self.validation_dock)

        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._update_mode_ui(edit_mode=False)
        self._update_window_title()
        self.statusBar().showMessage(f"Loaded {self.config_path}")

    def set_communicator(self, communicator: Any | None) -> None:
        self.controller.set_communicator(communicator)

    # ------------------------------------------------------------------
    # Actions / menus / toolbar
    # ------------------------------------------------------------------
    def _create_actions(self) -> None:
        self.load_config_action = QtWidgets.QAction("Load Panel Config...", self)
        self.load_config_action.triggered.connect(self._load_config_dialog)
        self.load_config_action.setShortcut("Ctrl+O")

        self.save_config_action = QtWidgets.QAction("Save Layout", self)
        self.save_config_action.triggered.connect(self._save_layout)
        self.save_config_action.setShortcut("Ctrl+S")

        self.save_config_as_action = QtWidgets.QAction("Save Layout As...", self)
        self.save_config_as_action.triggered.connect(self._save_layout_as)
        self.save_config_as_action.setShortcut("Ctrl+Shift+S")

        self.edit_layout_action = QtWidgets.QAction("Edit Layout", self)
        self.edit_layout_action.setCheckable(True)
        self.edit_layout_action.toggled.connect(self._on_edit_layout_toggled)
        self.edit_layout_action.setShortcut("Ctrl+E")

        self.undo_action = QtWidgets.QAction("Undo", self)
        self.undo_action.triggered.connect(self.canvas.undo)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.setEnabled(False)

        self.redo_action = QtWidgets.QAction("Redo", self)
        self.redo_action.triggered.connect(self.canvas.redo)
        self.redo_action.setShortcut("Ctrl+Y")
        self.redo_action.setEnabled(False)

        self.add_element_action = QtWidgets.QAction("Add Element...", self)
        self.add_element_action.triggered.connect(self._add_element_dialog)
        self.add_element_action.setShortcut("Ctrl+N")

        self.edit_selected_action = QtWidgets.QAction("Edit Selected...", self)
        self.edit_selected_action.triggered.connect(self._edit_selected_dialog)
        self.edit_selected_action.setShortcut("Return")

        self.add_pipe_action = QtWidgets.QAction("Add Pipe", self)
        self.add_pipe_action.setCheckable(True)
        self.add_pipe_action.triggered.connect(self._toggle_pipe_creation)
        self.add_pipe_action.setShortcut("Ctrl+P")

        self.rotate_selected_action = QtWidgets.QAction("Rotate Selected 90°", self)
        self.rotate_selected_action.triggered.connect(lambda: self.canvas.rotate_selected(90.0))
        self.rotate_selected_action.setShortcut("R")

        self.delete_selected_action = QtWidgets.QAction("Delete Selected", self)
        self.delete_selected_action.triggered.connect(self.canvas.delete_selected)
        self.delete_selected_action.setShortcut("Delete")

        self.show_grid_action = QtWidgets.QAction("Show Grid", self)
        self.show_grid_action.setCheckable(True)
        self.show_grid_action.setChecked(True)
        self.show_grid_action.toggled.connect(self.canvas.set_show_grid)

        self.snap_to_grid_action = QtWidgets.QAction("Snap to Grid", self)
        self.snap_to_grid_action.setCheckable(True)
        self.snap_to_grid_action.setChecked(True)
        self.snap_to_grid_action.toggled.connect(self.canvas.set_snap_to_grid)

        self.grid_spacing_action = QtWidgets.QAction("Grid Spacing...", self)
        self.grid_spacing_action.triggered.connect(self._set_grid_spacing_dialog)

        self.fit_to_window_action = QtWidgets.QAction("Fit to Window", self)
        self.fit_to_window_action.triggered.connect(self.canvas.fit_to_window)
        self.fit_to_window_action.setShortcut("Ctrl+0")

        self.zoom_in_action = QtWidgets.QAction("Zoom In", self)
        self.zoom_in_action.triggered.connect(lambda: self.canvas.zoom_by(1.2))
        self.zoom_in_action.setShortcut("Ctrl++")

        self.zoom_out_action = QtWidgets.QAction("Zoom Out", self)
        self.zoom_out_action.triggered.connect(lambda: self.canvas.zoom_by(1.0 / 1.2))
        self.zoom_out_action.setShortcut("Ctrl+-")

        self.align_left_action = QtWidgets.QAction("Align Left", self)
        self.align_left_action.triggered.connect(lambda: self.canvas.align_selected("left"))
        self.align_right_action = QtWidgets.QAction("Align Right", self)
        self.align_right_action.triggered.connect(lambda: self.canvas.align_selected("right"))
        self.align_top_action = QtWidgets.QAction("Align Top", self)
        self.align_top_action.triggered.connect(lambda: self.canvas.align_selected("top"))
        self.align_bottom_action = QtWidgets.QAction("Align Bottom", self)
        self.align_bottom_action.triggered.connect(lambda: self.canvas.align_selected("bottom"))
        self.align_center_x_action = QtWidgets.QAction("Align Center X", self)
        self.align_center_x_action.triggered.connect(lambda: self.canvas.align_selected("center_x"))
        self.align_center_y_action = QtWidgets.QAction("Align Center Y", self)
        self.align_center_y_action.triggered.connect(lambda: self.canvas.align_selected("center_y"))
        self.distribute_horizontal_action = QtWidgets.QAction("Distribute Horizontally", self)
        self.distribute_horizontal_action.triggered.connect(lambda: self.canvas.distribute_selected("horizontal"))
        self.distribute_vertical_action = QtWidgets.QAction("Distribute Vertically", self)
        self.distribute_vertical_action.triggered.connect(lambda: self.canvas.distribute_selected("vertical"))

        self.close_all_action = QtWidgets.QAction("Close/Deactivate All", self)
        self.close_all_action.triggered.connect(self._close_all_elements)

        self.quit_action = QtWidgets.QAction("Quit", self)
        self.quit_action.triggered.connect(self.close)
        self.quit_action.setShortcut("Ctrl+Q")

        self._editing_actions = [
            self.undo_action,
            self.redo_action,
            self.add_element_action,
            self.add_pipe_action,
            self.edit_selected_action,
            self.rotate_selected_action,
            self.delete_selected_action,
            self.show_grid_action,
            self.snap_to_grid_action,
            self.grid_spacing_action,
            self.fit_to_window_action,
            self.zoom_in_action,
            self.zoom_out_action,
            self.align_left_action,
            self.align_right_action,
            self.align_top_action,
            self.align_bottom_action,
            self.align_center_x_action,
            self.align_center_y_action,
            self.distribute_horizontal_action,
            self.distribute_vertical_action,
        ]

    def _create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction(self.load_config_action)
        file_menu.addAction(self.save_config_action)
        file_menu.addAction(self.save_config_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)

        panel_menu = self.menuBar().addMenu("Panel")
        panel_menu.addAction(self.close_all_action)
        panel_menu.addSeparator()
        panel_menu.addAction(self.edit_layout_action)
        panel_menu.addAction(self.add_element_action)
        panel_menu.addAction(self.add_pipe_action)
        panel_menu.addAction(self.edit_selected_action)
        panel_menu.addAction(self.rotate_selected_action)
        panel_menu.addAction(self.delete_selected_action)

        edit_menu = self.menuBar().addMenu("Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.show_grid_action)
        edit_menu.addAction(self.snap_to_grid_action)
        edit_menu.addAction(self.grid_spacing_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.fit_to_window_action)
        edit_menu.addAction(self.zoom_in_action)
        edit_menu.addAction(self.zoom_out_action)

        align_menu = self.menuBar().addMenu("Align")
        for action in (
            self.align_left_action,
            self.align_right_action,
            self.align_top_action,
            self.align_bottom_action,
            self.align_center_x_action,
            self.align_center_y_action,
            self.distribute_horizontal_action,
            self.distribute_vertical_action,
        ):
            align_menu.addAction(action)

        help_menu = self.menuBar().addMenu("Help")
        shortcuts_action = QtWidgets.QAction("Editing Shortcuts", self)
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)

    def _create_toolbar(self) -> None:
        self.toolbar = self.addToolBar("Panel")
        self.toolbar.setMovable(False)
        self.toolbar.addAction(self.close_all_action)
        self.toolbar.addAction(self.edit_layout_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.save_config_action)

        self.editor_toolbar = self.addToolBar("Layout Editor")
        self.editor_toolbar.setMovable(False)
        self.editor_toolbar.addAction(self.undo_action)
        self.editor_toolbar.addAction(self.redo_action)
        self.editor_toolbar.addSeparator()
        self.editor_toolbar.addAction(self.add_element_action)
        self.editor_toolbar.addAction(self.add_pipe_action)
        self.editor_toolbar.addAction(self.edit_selected_action)
        self.editor_toolbar.addAction(self.rotate_selected_action)
        self.editor_toolbar.addAction(self.delete_selected_action)
        self.editor_toolbar.addSeparator()
        self.editor_toolbar.addAction(self.show_grid_action)
        self.editor_toolbar.addAction(self.snap_to_grid_action)
        self.editor_toolbar.addAction(self.fit_to_window_action)
        self.editor_toolbar.addSeparator()
        self.editor_toolbar.addAction(self.align_left_action)
        self.editor_toolbar.addAction(self.align_right_action)
        self.editor_toolbar.addAction(self.align_top_action)
        self.editor_toolbar.addAction(self.align_bottom_action)
        self.editor_toolbar.addAction(self.distribute_horizontal_action)
        self.editor_toolbar.addAction(self.distribute_vertical_action)

    # ------------------------------------------------------------------
    # File/config actions
    # ------------------------------------------------------------------
    def _maybe_save_dirty(self) -> bool:
        if not self._dirty:
            return True
        response = QtWidgets.QMessageBox.question(
            self,
            "Save layout changes?",
            "The layout has unsaved changes. Save before continuing?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel,
        )
        if response == QtWidgets.QMessageBox.Cancel:
            return False
        if response == QtWidgets.QMessageBox.Yes:
            self._save_layout()
        return True

    def _load_config_dialog(self) -> None:
        if not self._maybe_save_dirty():
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load panel config",
            str(self.config_path.parent),
            "YAML files (*.yaml *.yml);;All files (*)",
        )
        if path:
            self._load_config(Path(path))

    def _load_config(self, path: Path) -> None:
        config = load_panel_config(path)
        self.config_path = path
        self.panel_config = config
        self.controller.set_panel_config(config)
        self.canvas.set_panel_config(config)
        self.properties_panel.set_panel_config(config)
        self.validation_panel.set_panel_config(config)
        self._dirty = False
        self._update_window_title()
        self.statusBar().showMessage(f"Loaded {path}")

    def _save_layout(self) -> None:
        save_panel_config(self.panel_config, self.config_path)
        self._dirty = False
        self._update_window_title()
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

    # ------------------------------------------------------------------
    # Mode and editor actions
    # ------------------------------------------------------------------
    def _update_mode_ui(self, *, edit_mode: bool) -> None:
        self.canvas.set_edit_mode(edit_mode)
        self.editor_toolbar.setVisible(edit_mode)
        self.properties_dock.setVisible(edit_mode)
        self.validation_dock.setVisible(edit_mode)
        self.close_all_action.setEnabled(not edit_mode)
        self.close_all_action.setVisible(not edit_mode)
        for action in getattr(self, "_editing_actions", []):
            action.setVisible(edit_mode)
            # Undo/redo need their own enable state once visible.
            if action not in (self.undo_action, self.redo_action):
                action.setEnabled(edit_mode)
        self.undo_action.setEnabled(edit_mode and self.canvas.can_undo())
        self.redo_action.setEnabled(edit_mode and self.canvas.can_redo())
        if not edit_mode and self.add_pipe_action.isChecked():
            self.add_pipe_action.blockSignals(True)
            self.add_pipe_action.setChecked(False)
            self.add_pipe_action.blockSignals(False)

    def _on_edit_layout_toggled(self, enabled: bool) -> None:
        self._update_mode_ui(edit_mode=enabled)
        if enabled:
            self.statusBar().showMessage("Edit mode enabled. Hardware toggle commands are disabled until runtime mode resumes.")
        else:
            self.statusBar().showMessage("Runtime mode enabled")

    def _on_canvas_edit_requested(self, kind: str, item_id: str) -> None:
        if not self.edit_layout_action.isChecked():
            self.edit_layout_action.setChecked(True)
        self._edit_selected_dialog()

    def _on_pipe_mode_changed(self, enabled: bool) -> None:
        if self.add_pipe_action.isChecked() != enabled:
            self.add_pipe_action.blockSignals(True)
            self.add_pipe_action.setChecked(enabled)
            self.add_pipe_action.blockSignals(False)

    def _on_selection_items_changed(self, selected_items: object) -> None:
        self.properties_panel.set_selection(list(selected_items))

    def _on_history_changed(self, can_undo: bool, can_redo: bool) -> None:
        edit_mode = self.edit_layout_action.isChecked() if hasattr(self, "edit_layout_action") else False
        self.undo_action.setEnabled(edit_mode and can_undo)
        self.redo_action.setEnabled(edit_mode and can_redo)

    def _on_layout_changed(self) -> None:
        self._dirty = True
        self._update_window_title()
        self.properties_panel.refresh()
        self.validation_panel.refresh()

    def _update_window_title(self) -> None:
        dirty = "*" if self._dirty else ""
        self.setWindowTitle(f"{dirty}{self.panel_config.title} — {self.config_path.name}")

    # ------------------------------------------------------------------
    # Editing actions
    # ------------------------------------------------------------------
    def _add_element_dialog(self) -> None:
        if not self.edit_layout_action.isChecked():
            self.edit_layout_action.setChecked(True)
        dialog = ElementDialog(
            panel_config=self.panel_config,
            default_center=self.canvas.center_of_visible_scene(),
            parent=self,
        )
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        self.canvas.add_element(dialog.result_element())

    def _edit_selected_dialog(self) -> None:
        if len(self.canvas.selected_items()) > 1:
            self.statusBar().showMessage("Multiple items selected. Use the Properties panel for bulk rotate/delete or select one item to edit fields.")
            return
        element = self.canvas.selected_element()
        if element is not None:
            dialog = ElementDialog(panel_config=self.panel_config, existing=element, parent=self)
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                self.canvas.update_element(element.id, dialog.result_element())
            return
        pipe = self.canvas.selected_pipe()
        if pipe is not None:
            dialog = PipeDialog(panel_config=self.panel_config, existing=pipe, parent=self)
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                self.canvas.update_pipe(pipe.id, dialog.result_pipe())
            return
        self.statusBar().showMessage("Select an element or pipe first")

    def _toggle_pipe_creation(self, checked: bool) -> None:
        if checked:
            if not self.edit_layout_action.isChecked():
                self.edit_layout_action.setChecked(True)
            self.canvas.begin_pipe_creation()
        else:
            self.canvas.end_pipe_creation()

    def _set_grid_spacing_dialog(self) -> None:
        spacing, accepted = QtWidgets.QInputDialog.getDouble(
            self,
            "Grid spacing",
            "Spacing in design units:",
            self.canvas.grid_spacing,
            2.0,
            500.0,
            1,
        )
        if accepted:
            self.canvas.set_grid_spacing(spacing)

    def _close_all_elements(self) -> None:
        try:
            self.canvas.set_all_elements_state(False, send=True)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Close all failed", str(exc))
            return
        self.statusBar().showMessage("Close/deactivate-all command sent")

    def _show_shortcuts(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "Editing shortcuts",
            "Runtime mode:\n"
            "  Click an enabled element to toggle it through the controller/communicator.\n"
            "  Close/Deactivate All is available only in runtime mode.\n\n"
            "Edit mode:\n"
            "  Ctrl+E: toggle edit mode\n"
            "  Ctrl+Z / Ctrl+Y: undo / redo\n"
            "  Ctrl+N: add a new element\n"
            "  Ctrl+P: add pipes by clicking endpoints\n"
            "  Click: select one item\n"
            "  Ctrl+click: add/remove item from selection\n"
            "  Drag empty canvas: box select\n"
            "  Drag selected items: move selection\n"
            "  Shift while dragging: constrain horizontal/vertical movement\n"
            "  Mouse wheel: zoom\n"
            "  Middle-drag or Space+left-drag: pan\n"
            "  R / Shift+R: rotate selected ±90°\n"
            "  Delete/Backspace: delete selected\n"
            "  Arrow keys: nudge selected; Shift+arrow: grid-step nudge\n"
            "  Esc: cancel pipe mode or clear selection\n"
            "  Ctrl+S: save layout",
        )

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        if not self._maybe_save_dirty():
            event.ignore()
            return
        super().closeEvent(event)
