from __future__ import annotations

"""Registry-wide actuator/relay validation browser used during valve editing."""

from PyQt5 import QtCore, QtGui, QtWidgets

from ..actuators import ActuatorRegistry
from ..models import PanelConfig


class ValidationPanel(QtWidgets.QWidget):
    """Show panel reference issues plus all actuator bindings in one place."""

    def __init__(
        self,
        *,
        actuator_registry: ActuatorRegistry,
        relay_count: int = 24,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.actuator_registry = actuator_registry
        self.relay_count = relay_count
        self.panel_config: PanelConfig | None = None

        self.summary_label = QtWidgets.QLabel("No layout loaded")
        self.summary_label.setWordWrap(True)
        self.message_list = QtWidgets.QListWidget()
        self.message_list.setAlternatingRowColors(True)

        self.relay_table = QtWidgets.QTableWidget(0, 5)
        self.relay_table.setHorizontalHeaderLabels(
            ["Device", "Relay", "Status", "Actuator", "Kind"]
        )
        self.relay_table.verticalHeader().setVisible(False)
        self.relay_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.relay_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.relay_table.horizontalHeader().setStretchLastSection(True)
        for column in (0, 1, 2):
            self.relay_table.horizontalHeader().setSectionResizeMode(
                column, QtWidgets.QHeaderView.ResizeToContents
            )

        tabs = QtWidgets.QTabWidget()
        validation_page = QtWidgets.QWidget()
        validation_layout = QtWidgets.QVBoxLayout(validation_page)
        validation_layout.addWidget(self.summary_label)
        validation_layout.addWidget(self.message_list)
        tabs.addTab(validation_page, "Validation")
        tabs.addTab(self.relay_table, "Actuator Registry")
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(tabs)

        self.actuator_registry.changed.connect(self.refresh)

    def set_panel_config(self, panel_config: PanelConfig) -> None:
        self.panel_config = panel_config
        self.refresh()

    def refresh(self) -> None:
        if self.panel_config is None:
            return

        messages = list(self.panel_config.validate_actuator_references())
        registry_ids = set(self.actuator_registry.definitions)
        for element in self.panel_config.elements:
            if element.actuator_id and element.actuator_id not in registry_ids:
                messages.append(
                    f"{element.id}: actuator {element.actuator_id!r} is missing from actuators.yaml"
                )
        messages.extend(self.actuator_registry.validate())

        definitions = self.actuator_registry.all()
        assigned_count = sum(d.relay_number is not None for d in definitions)
        if messages:
            self.summary_label.setText(
                f"⚠ {len(messages)} actuator issue(s). "
                f"{assigned_count}/{len(definitions)} actuators have relay bindings."
            )
        else:
            self.summary_label.setText(
                f"✓ Actuator registry valid. {assigned_count}/{len(definitions)} actuators bound."
            )

        self.message_list.clear()
        if messages:
            self.message_list.addItems(messages)
        else:
            self.message_list.addItem("No actuator or relay binding issues detected.")

        usage = self.actuator_registry.relay_usage()
        devices = sorted({d.device_id for d in definitions} or {"controller"})
        rows: list[tuple[str, int, list]] = []
        for device_id in devices:
            for relay in range(1, self.relay_count + 1):
                rows.append((device_id, relay, usage.get((device_id, relay), [])))
        self.relay_table.setRowCount(len(rows))

        for row, (device_id, relay, owners) in enumerate(rows):
            if not owners:
                status = "Available"
                actuator_names = ""
                kinds = ""
                bg = QtGui.QColor(245, 245, 245)
            elif len(owners) == 1:
                status = "Assigned"
                actuator_names = owners[0].actuator_id
                kinds = owners[0].kind
                bg = QtGui.QColor(226, 245, 228)
            else:
                status = "Duplicate"
                actuator_names = ", ".join(owner.actuator_id for owner in owners)
                kinds = ", ".join(owner.kind for owner in owners)
                bg = QtGui.QColor(255, 235, 235)

            for col, value in enumerate(
                (device_id, str(relay), status, actuator_names, kinds)
            ):
                item = QtWidgets.QTableWidgetItem(value)
                item.setBackground(bg)
                if col in (1, 2):
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.relay_table.setItem(row, col, item)
