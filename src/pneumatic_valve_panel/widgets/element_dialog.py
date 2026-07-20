from __future__ import annotations

from PyQt5 import QtCore, QtWidgets

from ..models import ActuatedElementConfig, PanelConfig


class ElementDialog(QtWidgets.QDialog):
    """Dialog for adding or editing an actuated panel element."""

    def __init__(
        self,
        *,
        panel_config: PanelConfig,
        existing: ActuatedElementConfig | None = None,
        default_center: tuple[float, float] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.panel_config = panel_config
        self.existing = existing
        self.default_center = default_center or (
            panel_config.design_width / 2.0,
            panel_config.design_height / 2.0,
        )
        self.setWindowTitle("Edit Element" if existing else "Add New Element")
        self.setModal(True)
        self._build_ui()
        self._populate()

    def result_element(self) -> ActuatedElementConfig:
        element_id = self.id_edit.text().strip()
        label = self.label_edit.text().strip() or element_id
        element_type = str(self.type_combo.currentData())
        width = float(self.width_spin.value())
        height = float(self.height_spin.value())
        relay_number = int(self.relay_spin.value())
        center = (
            float(self.x_spin.value()),
            float(self.y_spin.value()),
        )
        return ActuatedElementConfig(
            id=element_id,
            label=label,
            element_type=element_type,
            center=center,
            size=(width, height),
            rotation=float(self.rotation_spin.value()),
            relay_number=relay_number,
            initially_active=self.initial_state_check.isChecked(),
            enabled=self.enabled_check.isChecked(),
            metadata=dict(self.existing.metadata) if self.existing is not None else {},
        )

    def accept(self) -> None:  # noqa: D401,N802 - Qt API name
        """Validate before closing."""
        element_id = self.id_edit.text().strip()
        if not element_id:
            QtWidgets.QMessageBox.warning(self, "Invalid element", "Element ID cannot be empty.")
            return

        duplicate = any(
            element.id == element_id
            and (self.existing is None or element.id != self.existing.id)
            for element in self.panel_config.elements
        )
        if duplicate:
            QtWidgets.QMessageBox.warning(
                self,
                "Duplicate element ID",
                f"An element with ID {element_id!r} already exists.",
            )
            return

        relay = int(self.relay_spin.value())
        used = self.panel_config.used_relays(
            exclude_element_id=self.existing.id if self.existing is not None else None
        )
        if relay in used:
            response = QtWidgets.QMessageBox.question(
                self,
                "Relay already used",
                f"Relay {relay} is already bound to another element. Use it anyway?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            if response != QtWidgets.QMessageBox.Yes:
                return

        super().accept()

    def _build_ui(self) -> None:
        form = QtWidgets.QFormLayout()

        self.id_edit = QtWidgets.QLineEdit()
        self.label_edit = QtWidgets.QLineEdit()

        self.type_combo = QtWidgets.QComboBox()
        for type_id, spec in self.panel_config.valve_types.items():
            self.type_combo.addItem(f"{spec.display_name}  [{spec.shape}]", type_id)

        self.relay_spin = QtWidgets.QSpinBox()
        self.relay_spin.setRange(1, 24)
        self.relay_spin.setToolTip("Relay number used by your external serial communicator. Valid range: 1-24.")

        self.x_spin = QtWidgets.QDoubleSpinBox()
        self.y_spin = QtWidgets.QDoubleSpinBox()
        for spin, maximum in (
            (self.x_spin, self.panel_config.design_width),
            (self.y_spin, self.panel_config.design_height),
        ):
            spin.setRange(-10000.0, max(10000.0, maximum * 2.0))
            spin.setDecimals(1)
            spin.setSingleStep(5.0)

        self.width_spin = QtWidgets.QDoubleSpinBox()
        self.height_spin = QtWidgets.QDoubleSpinBox()
        for spin in (self.width_spin, self.height_spin):
            spin.setRange(10.0, 500.0)
            spin.setDecimals(1)
            spin.setSingleStep(5.0)

        self.rotation_spin = QtWidgets.QDoubleSpinBox()
        self.rotation_spin.setRange(0.0, 359.0)
        self.rotation_spin.setDecimals(1)
        self.rotation_spin.setSingleStep(15.0)
        self.rotation_spin.setSuffix("°")

        self.initial_state_check = QtWidgets.QCheckBox("Start active/open")
        self.enabled_check = QtWidgets.QCheckBox("Enabled")
        self.enabled_check.setChecked(True)

        self.used_relays_label = QtWidgets.QLabel()
        self.used_relays_label.setWordWrap(True)

        form.addRow("Element ID", self.id_edit)
        form.addRow("Label", self.label_edit)
        form.addRow("Element type", self.type_combo)
        form.addRow("Relay binding", self.relay_spin)
        form.addRow("X center", self.x_spin)
        form.addRow("Y center", self.y_spin)
        form.addRow("Width", self.width_spin)
        form.addRow("Height", self.height_spin)
        form.addRow("Rotation", self.rotation_spin)
        form.addRow("Initial state", self.initial_state_check)
        form.addRow("Enabled", self.enabled_check)
        form.addRow("Used relays", self.used_relays_label)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _populate(self) -> None:
        used = sorted(self.panel_config.used_relays(
            exclude_element_id=self.existing.id if self.existing else None
        ))
        self.used_relays_label.setText(
            ", ".join(str(relay) for relay in used) if used else "None"
        )

        if self.existing is None:
            element_id = self.panel_config.next_element_id("element")
            self.id_edit.setText(element_id)
            self.label_edit.setText(element_id)
            self.x_spin.setValue(self.default_center[0])
            self.y_spin.setValue(self.default_center[1])
            self.width_spin.setValue(self.panel_config.default_element_size[0])
            self.height_spin.setValue(self.panel_config.default_element_size[1])

            for relay in range(1, 25):
                if relay not in set(used):
                    self.relay_spin.setValue(relay)
                    break
            return

        self.id_edit.setText(self.existing.id)
        self.label_edit.setText(self.existing.label)
        for index in range(self.type_combo.count()):
            if self.type_combo.itemData(index) == self.existing.element_type:
                self.type_combo.setCurrentIndex(index)
                break
        if self.existing.relay_number is not None:
            self.relay_spin.setValue(int(self.existing.relay_number))
        self.x_spin.setValue(self.existing.center[0])
        self.y_spin.setValue(self.existing.center[1])
        self.width_spin.setValue(self.existing.size[0])
        self.height_spin.setValue(self.existing.size[1])
        self.rotation_spin.setValue(self.existing.rotation % 360.0)
        self.initial_state_check.setChecked(self.existing.initially_active)
        self.enabled_check.setChecked(self.existing.enabled)
