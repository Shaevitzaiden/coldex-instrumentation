from __future__ import annotations

from collections.abc import Iterable

from PyQt5 import QtWidgets

from .tile_base import TileWidget


class ValvePanelTile(TileWidget):
    """Valve panel tile with its own runtime and edit controls.

    Valve-specific actions live here rather than on MainWindow. The main window
    still owns the QAction objects so shortcuts and application state remain
    centralized, but the visible controls are attached to the valve panel dock.
    """

    def __init__(
        self,
        *,
        tile_id: str,
        title: str,
        canvas: QtWidgets.QWidget,
        close_all_action: QtWidgets.QAction,
        edit_layout_action: QtWidgets.QAction,
        save_config_action: QtWidgets.QAction,
        save_config_as_action: QtWidgets.QAction,
        undo_action: QtWidgets.QAction,
        redo_action: QtWidgets.QAction,
        add_element_action: QtWidgets.QAction,
        add_pipe_action: QtWidgets.QAction,
        edit_selected_action: QtWidgets.QAction,
        rotate_selected_action: QtWidgets.QAction,
        delete_selected_action: QtWidgets.QAction,
        show_grid_action: QtWidgets.QAction,
        snap_to_grid_action: QtWidgets.QAction,
        grid_spacing_action: QtWidgets.QAction,
        fit_to_window_action: QtWidgets.QAction,
        zoom_in_action: QtWidgets.QAction,
        zoom_out_action: QtWidgets.QAction,
        alignment_actions: Iterable[QtWidgets.QAction],
        removable: bool = True,
    ) -> None:
        self.canvas = canvas
        self.runtime_toolbar = QtWidgets.QToolBar("Valve Runtime Controls")
        self.runtime_toolbar.setIconSize(self.runtime_toolbar.iconSize())
        self.runtime_toolbar.setMovable(False)
        self.runtime_toolbar.addAction(close_all_action)
        self.runtime_toolbar.addAction(edit_layout_action)

        self.editor_toolbar = QtWidgets.QToolBar("Valve Layout Editor")
        self.editor_toolbar.setMovable(False)
        self.editor_toolbar.addAction(save_config_action)
        self.editor_toolbar.addAction(save_config_as_action)
        self.editor_toolbar.addSeparator()
        self.editor_toolbar.addAction(undo_action)
        self.editor_toolbar.addAction(redo_action)
        self.editor_toolbar.addSeparator()
        self.editor_toolbar.addAction(add_element_action)
        self.editor_toolbar.addAction(add_pipe_action)
        self.editor_toolbar.addAction(edit_selected_action)
        self.editor_toolbar.addAction(rotate_selected_action)
        self.editor_toolbar.addAction(delete_selected_action)
        self.editor_toolbar.addSeparator()
        self.editor_toolbar.addAction(show_grid_action)
        self.editor_toolbar.addAction(snap_to_grid_action)
        self.editor_toolbar.addAction(grid_spacing_action)
        self.editor_toolbar.addAction(fit_to_window_action)
        self.editor_toolbar.addAction(zoom_in_action)
        self.editor_toolbar.addAction(zoom_out_action)
        self.editor_toolbar.addSeparator()
        for action in alignment_actions:
            self.editor_toolbar.addAction(action)

        content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.runtime_toolbar)
        content_layout.addWidget(self.editor_toolbar)
        content_layout.addWidget(canvas, 1)

        super().__init__(tile_id=tile_id, title=title, child=content, removable=removable)
        self.set_valve_edit_mode(False)

    def set_valve_edit_mode(self, enabled: bool) -> None:
        enabled = bool(enabled)
        self.editor_toolbar.setVisible(enabled)
        self.runtime_toolbar.setVisible(True)
