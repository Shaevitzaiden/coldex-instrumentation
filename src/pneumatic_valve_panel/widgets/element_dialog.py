from __future__ import annotations

"""Add/edit dialog for pneumatic schematic elements.

The visual element owns geometry and a logical ``actuator_id``.  The physical
``device_id``/``relay_number`` pair is edited through the central
ActuatorRegistry so no relay binding is duplicated in valve_panel.yaml.
"""

from PyQt5 import QtWidgets

from ..actuators import ActuatorDefinition, ActuatorRegistry
from ..data.models import DeviceDefinition
from ..models import ActuatedElementConfig, PanelConfig


class ElementDialog(QtWidgets.QDialog):
    """Dialog for adding/editing a pneumatic element and its actuator binding."""

    def __init__(
        self,
        *,
        panel_config: PanelConfig,
        actuator_registry: ActuatorRegistry,
        device_definitions: dict[str, DeviceDefinition],
        existing: ActuatedElementConfig | None = None,
        default_center: tuple[float, float] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.panel_config = panel_config
        self.actuator_registry = actuator_registry
        self.device_definitions = dict(device_definitions)
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
        return ActuatedElementConfig(
            id=element_id,
            label=label,
            element_type=str(self.type_combo.currentData()),
            center=(float(self.x_spin.value()), float(self.y_spin.value())),
            size=(float(self.width_spin.value()), float(self.height_spin.value())),
            rotation=float(self.rotation_spin.value()),
            actuator_id=self.actuator_id_edit.text().strip() or None,
            initially_active=self.initial_state_check.isChecked(),
            enabled=self.enabled_check.isChecked(),
            locked=self.locked_check.isChecked(),
            metadata={
                key: value
                for key, value in (
                    dict(self.existing.metadata) if self.existing is not None else {}
                ).items()
                if key != "_legacy_relay_number"
            },
        )

    def accept(self) -> None:  # noqa: N802 - Qt API
        element_id = self.id_edit.text().strip()
        actuator_id = self.actuator_id_edit.text().strip()
        if not element_id:
            QtWidgets.QMessageBox.warning(self, "Invalid element", "Element ID cannot be empty.")
            return
        if not actuator_id:
            QtWidgets.QMessageBox.warning(self, "Invalid actuator", "Actuator ID cannot be empty.")
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

        # Prevent two schematic elements from silently controlling the same
        # logical actuator.  Shared physical outputs should be represented by
        # one actuator and one intentional UI owner.
        for element in self.panel_config.elements:
            if self.existing is not None and element.id == self.existing.id:
                continue
            if element.actuator_id == actuator_id:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Actuator already used",
                    f"Actuator {actuator_id!r} is already referenced by panel element {element.id!r}.",
                )
                return

        device_id = str(self.device_combo.currentData() or self.device_combo.currentText()).strip()
        relay = self.relay_spin.value() or None

        existing_actuator = self.actuator_registry.maybe_get(actuator_id)
        if (
            existing_actuator is not None
            and existing_actuator.kind in {"crusher_solenoid", "crusher"}
            and (self.existing is None or self.existing.actuator_id != actuator_id)
        ):
            QtWidgets.QMessageBox.warning(
                self,
                "Actuator belongs to crusher hardware",
                f"Actuator {actuator_id!r} is reserved for crusher control.",
            )
            return

        # Build the complete desired registry entry first and apply it in one
        # atomic operation.  This avoids the old failure mode where creating a
        # new actuator succeeded but a later relay-conflict check failed, leaving
        # a phantom unbound actuator behind even though the dialog stayed open.
        candidate = ActuatorDefinition(
            actuator_id=actuator_id,
            label=self.label_edit.text().strip() or element_id,
            kind=str(self.type_combo.currentData()),
            device_id=device_id or "controller",
            relay_number=relay,
            enabled=self.enabled_check.isChecked(),
            default_active=self.initial_state_check.isChecked(),
            metadata=(dict(existing_actuator.metadata) if existing_actuator else {}),
        )
        try:
            self.actuator_registry.upsert(candidate)
        except (KeyError, ValueError) as exc:
            QtWidgets.QMessageBox.warning(self, "Invalid actuator binding", str(exc))
            return

        super().accept()

    def _build_ui(self) -> None:
        form = QtWidgets.QFormLayout()
        self.id_edit = QtWidgets.QLineEdit()
        self.label_edit = QtWidgets.QLineEdit()
        self.type_combo = QtWidgets.QComboBox()
        for type_id, spec in self.panel_config.valve_types.items():
            self.type_combo.addItem(f"{spec.display_name}  [{spec.shape}]", type_id)

        self.actuator_id_edit = QtWidgets.QLineEdit()
        self.actuator_id_edit.setToolTip(
            "Logical actuator name stored in valve_panel.yaml and resolved through actuators.yaml."
        )
        self.device_combo = QtWidgets.QComboBox()
        for device_id, definition in self.device_definitions.items():
            if definition.enabled:
                self.device_combo.addItem(device_id, device_id)
        if self.device_combo.count() == 0:
            self.device_combo.addItem("controller", "controller")

        self.relay_spin = QtWidgets.QSpinBox()
        self.relay_spin.setRange(0, self.actuator_registry.relay_count)
        self.relay_spin.setSpecialValueText("Unassigned")
        self.used_relays_label = QtWidgets.QLabel()
        self.used_relays_label.setWordWrap(True)

        self.x_spin = self._double_spin(-10000, 10000, 1)
        self.y_spin = self._double_spin(-10000, 10000, 1)
        self.width_spin = self._double_spin(5, 2000, 1)
        self.height_spin = self._double_spin(5, 2000, 1)
        self.rotation_spin = self._double_spin(0, 359, 1)
        self.rotation_spin.setSuffix("°")
        self.initial_state_check = QtWidgets.QCheckBox("Active/open")
        self.locked_check = QtWidgets.QCheckBox("Locked")
        self.enabled_check = QtWidgets.QCheckBox("Enabled")
        self.enabled_check.setChecked(True)

        form.addRow("Element ID", self.id_edit)
        form.addRow("Label", self.label_edit)
        form.addRow("Type", self.type_combo)
        form.addRow("Actuator ID", self.actuator_id_edit)
        form.addRow("Device", self.device_combo)
        form.addRow("Relay", self.relay_spin)
        form.addRow("Other relay assignments", self.used_relays_label)
        form.addRow("X", self.x_spin)
        form.addRow("Y", self.y_spin)
        form.addRow("Width", self.width_spin)
        form.addRow("Height", self.height_spin)
        form.addRow("Rotation", self.rotation_spin)
        form.addRow("Initial state", self.initial_state_check)
        form.addRow("Locked", self.locked_check)
        form.addRow("Enabled", self.enabled_check)

        self.device_combo.currentIndexChanged.connect(self._refresh_used_relays)
        self.actuator_id_edit.textChanged.connect(self._on_actuator_id_changed)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _double_spin(self, minimum: float, maximum: float, decimals: int) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        return spin

    def _populate(self) -> None:
        if self.existing is None:
            element_id = self.panel_config.next_element_id("element")
            self.id_edit.setText(element_id)
            self.label_edit.setText(element_id)
            self.actuator_id_edit.setText(element_id)
            self.x_spin.setValue(self.default_center[0])
            self.y_spin.setValue(self.default_center[1])
            self.width_spin.setValue(self.panel_config.default_element_size[0])
            self.height_spin.setValue(self.panel_config.default_element_size[1])
            self._select_default_device()
            self._choose_first_available_relay()
            self._refresh_used_relays()
            return

        self.id_edit.setText(self.existing.id)
        self.label_edit.setText(self.existing.label)
        type_index = self.type_combo.findData(self.existing.element_type)
        if type_index >= 0:
            self.type_combo.setCurrentIndex(type_index)
        actuator_id = self.existing.actuator_id or self.existing.id
        self.actuator_id_edit.setText(actuator_id)
        actuator = self.actuator_registry.maybe_get(actuator_id)
        if actuator is not None:
            device_index = self.device_combo.findData(actuator.device_id)
            if device_index >= 0:
                self.device_combo.setCurrentIndex(device_index)
            self.relay_spin.setValue(actuator.relay_number or 0)
        else:
            self._select_default_device()
        self.x_spin.setValue(self.existing.center[0])
        self.y_spin.setValue(self.existing.center[1])
        self.width_spin.setValue(self.existing.size[0])
        self.height_spin.setValue(self.existing.size[1])
        self.rotation_spin.setValue(self.existing.rotation % 360.0)
        self.initial_state_check.setChecked(self.existing.initially_active)
        self.locked_check.setChecked(self.existing.locked)
        self.enabled_check.setChecked(self.existing.enabled)
        self._refresh_used_relays()


    def _on_actuator_id_changed(self, actuator_id: str) -> None:
        """Refresh binding hints when the logical actuator reference changes."""

        actuator = self.actuator_registry.maybe_get(actuator_id.strip())
        if actuator is not None:
            index = self.device_combo.findData(actuator.device_id)
            if index >= 0:
                self.device_combo.setCurrentIndex(index)
            self.relay_spin.setValue(actuator.relay_number or 0)
        self._refresh_used_relays()

    def _select_default_device(self) -> None:
        command_targets = [d.device_id for d in self.device_definitions.values() if d.command_target]
        desired = command_targets[0] if command_targets else "controller"
        index = self.device_combo.findData(desired)
        if index >= 0:
            self.device_combo.setCurrentIndex(index)

    def _choose_first_available_relay(self) -> None:
        device_id = str(self.device_combo.currentData() or "controller")
        available = self.actuator_registry.available_relays(device_id)
        self.relay_spin.setValue(available[0] if available else 0)

    def _refresh_used_relays(self) -> None:
        device_id = str(self.device_combo.currentData() or "controller")
        current_id = self.actuator_id_edit.text().strip() or None
        usage = self.actuator_registry.relay_usage(device_id)
        labels = []
        for (_device, relay), owners in sorted(usage.items()):
            names = [owner.actuator_id for owner in owners if owner.actuator_id != current_id]
            if names:
                labels.append(f"R{relay}: {', '.join(names)}")
        self.used_relays_label.setText("; ".join(labels) if labels else "None")
