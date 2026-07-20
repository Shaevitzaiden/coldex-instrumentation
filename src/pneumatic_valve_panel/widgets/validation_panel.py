from __future__ import annotations

from PyQt5 import QtCore, QtGui, QtWidgets

from ..models import PanelConfig


class ValidationPanel(QtWidgets.QWidget):
    """Relay-binding browser plus layout validation messages."""

    def __init__(self, *, relay_count: int = 24, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.relay_count = relay_count
        self.panel_config: PanelConfig | None = None

        self.summary_label = QtWidgets.QLabel("No layout loaded")
        self.summary_label.setWordWrap(True)

        self.message_list = QtWidgets.QListWidget()
        self.message_list.setAlternatingRowColors(True)

        self.relay_table = QtWidgets.QTableWidget(relay_count, 3)
        self.relay_table.setHorizontalHeaderLabels(["Relay", "Status", "Element(s)"])
        self.relay_table.verticalHeader().setVisible(False)
        self.relay_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.relay_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.relay_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.relay_table.horizontalHeader().setStretchLastSection(True)
        self.relay_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        self.relay_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)

        tabs = QtWidgets.QTabWidget()
        validation_page = QtWidgets.QWidget()
        validation_layout = QtWidgets.QVBoxLayout(validation_page)
        validation_layout.addWidget(self.summary_label)
        validation_layout.addWidget(self.message_list)
        tabs.addTab(validation_page, "Validation")
        tabs.addTab(self.relay_table, "Relays")

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(tabs)

    def set_panel_config(self, panel_config: PanelConfig) -> None:
        self.panel_config = panel_config
        self.refresh()

    def refresh(self) -> None:
        if self.panel_config is None:
            return

        messages = self.panel_config.validate_relays(relay_count=self.relay_count)
        used_count = len(self.panel_config.relay_usage())
        unused = self.panel_config.unused_relays(relay_count=self.relay_count)
        if messages:
            self.summary_label.setText(
                f"⚠ {len(messages)} layout issue(s). "
                f"{used_count}/{self.relay_count} relays used; {len(unused)} unused."
            )
        else:
            self.summary_label.setText(
                f"✓ Relay bindings valid. {used_count}/{self.relay_count} relays used; {len(unused)} unused."
            )

        self.message_list.clear()
        if messages:
            for message in messages:
                self.message_list.addItem(message)
        else:
            self.message_list.addItem("No relay binding issues detected.")

        usage = self.panel_config.relay_usage()
        for row, relay in enumerate(range(1, self.relay_count + 1)):
            assigned = usage.get(relay, [])
            relay_item = QtWidgets.QTableWidgetItem(str(relay))
            if not assigned:
                status = "Available"
                element_names = ""
                bg = QtGui.QColor(245, 245, 245)
            elif len(assigned) == 1:
                status = "Assigned"
                element_names = assigned[0].id
                bg = QtGui.QColor(226, 245, 228)
            else:
                status = "Duplicate"
                element_names = ", ".join(element.id for element in assigned)
                bg = QtGui.QColor(255, 235, 235)

            for col, value in enumerate((str(relay), status, element_names)):
                item = QtWidgets.QTableWidgetItem(value)
                item.setBackground(bg)
                if col == 0:
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.relay_table.setItem(row, col, item)
