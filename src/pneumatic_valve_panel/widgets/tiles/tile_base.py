from __future__ import annotations

from PyQt5 import QtCore, QtWidgets


class TileWidget(QtWidgets.QFrame):
    """Framed dashboard panel with edit-only layout controls.

    The title remains visible in runtime mode, but geometry controls are hidden.
    This keeps the operational dashboard clear while making the editing mode
    discoverable and predictable.
    """

    close_requested = QtCore.pyqtSignal(str)
    configure_requested = QtCore.pyqtSignal(str)

    def __init__(
        self,
        *,
        tile_id: str,
        title: str,
        child: QtWidgets.QWidget,
        removable: bool = True,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tile_id = tile_id
        self.removable = removable
        self.child = child
        self.setObjectName(f"DashboardTile_{tile_id}")
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Plain)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        self.title_label = QtWidgets.QLabel(title)
        font = self.title_label.font()
        font.setBold(True)
        self.title_label.setFont(font)

        self.configure_button = QtWidgets.QToolButton()
        self.configure_button.setText("⚙")
        self.configure_button.setToolTip("Configure this panel's grid position and contents")
        self.configure_button.clicked.connect(lambda: self.configure_requested.emit(self.tile_id))

        self.close_button = QtWidgets.QToolButton()
        self.close_button.setText("×")
        self.close_button.setToolTip("Remove this panel from the dashboard")
        self.close_button.clicked.connect(lambda: self.close_requested.emit(self.tile_id))

        self.header = QtWidgets.QWidget()
        self.header.setObjectName("DashboardTileHeader")
        header_layout = QtWidgets.QHBoxLayout(self.header)
        header_layout.setContentsMargins(6, 2, 3, 2)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)
        header_layout.addWidget(self.configure_button)
        header_layout.addWidget(self.close_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        layout.addWidget(self.header)
        layout.addWidget(child, 1)
        self.set_dashboard_edit_mode(False)

    def title(self) -> str:
        return self.title_label.text()

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def set_dashboard_edit_mode(self, enabled: bool) -> None:
        enabled = bool(enabled)
        self.configure_button.setVisible(enabled)
        self.close_button.setVisible(enabled and self.removable)
        self.header.setStyleSheet(
            "#DashboardTileHeader { background: #e8eef8; border: 1px dashed #6688aa; }"
            if enabled
            else "#DashboardTileHeader { background: palette(window); border: none; }"
        )
