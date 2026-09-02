from __future__ import annotations

from PyQt5 import QtCore, QtWidgets

from ..actuators import ActuatorDefinition, ActuatorRegistry
from ..data.models import DeviceDefinition
from ..models import ActuatedElementConfig, PanelConfig, PipeConfig

SelectionItem = tuple[str, str]


class PropertiesPanel(QtWidgets.QWidget):
    """Persistent editor for the currently selected canvas item."""

    element_changed = QtCore.pyqtSignal(str, object)  # original_id, ActuatedElementConfig
    pipe_changed = QtCore.pyqtSignal(str, object)  # original_id, PipeConfig
    delete_requested = QtCore.pyqtSignal()
    rotate_requested = QtCore.pyqtSignal(float)

    def __init__(
        self,
        *,
        actuator_registry: ActuatorRegistry,
        device_definitions: dict[str, DeviceDefinition],
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.actuator_registry = actuator_registry
        self.device_definitions = dict(device_definitions)
        self.panel_config: PanelConfig | None = None
        self.selected_items: list[SelectionItem] = []
        self._loading = False

        self.stack = QtWidgets.QStackedWidget()
        self.none_page = self._build_none_page()
        self.multi_page = self._build_multi_page()
        self.element_page = self._build_element_page()
        self.pipe_page = self._build_pipe_page()
        self.stack.addWidget(self.none_page)
        self.stack.addWidget(self.multi_page)
        self.stack.addWidget(self.element_page)
        self.stack.addWidget(self.pipe_page)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.stack)

    def set_panel_config(self, panel_config: PanelConfig) -> None:
        self.panel_config = panel_config
        self.refresh()

    def set_selection(self, selected_items: list[SelectionItem]) -> None:
        self.selected_items = list(selected_items)
        self.refresh()

    def refresh(self) -> None:
        if self.panel_config is None:
            self.stack.setCurrentWidget(self.none_page)
            return
        self._loading = True
        try:
            if not self.selected_items:
                self.stack.setCurrentWidget(self.none_page)
                return
            if len(self.selected_items) > 1:
                self.multi_label.setText(f"{len(self.selected_items)} items selected")
                self.stack.setCurrentWidget(self.multi_page)
                return
            kind, item_id = self.selected_items[0]
            if kind == "element":
                self._populate_element(self.panel_config.element_by_id(item_id))
                self.stack.setCurrentWidget(self.element_page)
            elif kind == "pipe":
                self._populate_pipe(self.panel_config.pipe_by_id(item_id))
                self.stack.setCurrentWidget(self.pipe_page)
            else:
                self.stack.setCurrentWidget(self.none_page)
        finally:
            self._loading = False

    def _build_none_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        label = QtWidgets.QLabel("Select an element or pipe to edit its properties.")
        label.setWordWrap(True)
        layout = QtWidgets.QVBoxLayout(page)
        layout.addWidget(label)
        layout.addStretch(1)
        return page

    def _build_multi_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        self.multi_label = QtWidgets.QLabel()
        self.multi_label.setWordWrap(True)
        rotate_left = QtWidgets.QPushButton("Rotate -90°")
        rotate_right = QtWidgets.QPushButton("Rotate +90°")
        delete_button = QtWidgets.QPushButton("Delete Selected")
        rotate_left.clicked.connect(lambda: self.rotate_requested.emit(-90.0))
        rotate_right.clicked.connect(lambda: self.rotate_requested.emit(90.0))
        delete_button.clicked.connect(self.delete_requested.emit)
        layout = QtWidgets.QVBoxLayout(page)
        layout.addWidget(self.multi_label)
        layout.addWidget(rotate_left)
        layout.addWidget(rotate_right)
        layout.addWidget(delete_button)
        layout.addStretch(1)
        return page

    def _build_element_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout()
        self.element_original_id = ""
        self.element_id_edit = QtWidgets.QLineEdit()
        self.element_label_edit = QtWidgets.QLineEdit()
        self.element_type_combo = QtWidgets.QComboBox()
        self.actuator_id_edit = QtWidgets.QLineEdit()
        self.device_combo = QtWidgets.QComboBox()
        for device_id, definition in self.device_definitions.items():
            if definition.enabled:
                self.device_combo.addItem(device_id, device_id)
        if self.device_combo.count() == 0:
            self.device_combo.addItem("controller", "controller")
        self.relay_combo = QtWidgets.QComboBox()
        self.device_combo.currentIndexChanged.connect(self._refresh_relay_combo_for_device)
        self.actuator_id_edit.editingFinished.connect(self._refresh_actuator_binding_fields)
        self.element_x = self._double_spin(-10000, 10000, 1)
        self.element_y = self._double_spin(-10000, 10000, 1)
        self.element_w = self._double_spin(10, 1000, 1)
        self.element_h = self._double_spin(10, 1000, 1)
        self.element_rotation = self._double_spin(0, 359, 1)
        self.element_rotation.setSuffix("°")
        self.element_state = QtWidgets.QCheckBox("Active/open")
        self.element_locked = QtWidgets.QCheckBox("Locked")
        self.element_locked.setToolTip("Locked elements cannot be toggled in runtime mode until unlocked.")
        self.element_enabled = QtWidgets.QCheckBox("Enabled")

        form.addRow("ID", self.element_id_edit)
        form.addRow("Label", self.element_label_edit)
        form.addRow("Type", self.element_type_combo)
        form.addRow("Actuator ID", self.actuator_id_edit)
        form.addRow("Device", self.device_combo)
        form.addRow("Relay", self.relay_combo)
        form.addRow("X", self.element_x)
        form.addRow("Y", self.element_y)
        form.addRow("Width", self.element_w)
        form.addRow("Height", self.element_h)
        form.addRow("Rotation", self.element_rotation)
        form.addRow("State", self.element_state)
        form.addRow("Locked", self.element_locked)
        form.addRow("Enabled", self.element_enabled)

        apply_button = QtWidgets.QPushButton("Apply")
        delete_button = QtWidgets.QPushButton("Delete")
        rotate_button = QtWidgets.QPushButton("Rotate +90°")
        apply_button.clicked.connect(self._emit_element_update)
        delete_button.clicked.connect(self.delete_requested.emit)
        rotate_button.clicked.connect(lambda: self.rotate_requested.emit(90.0))

        button_row = QtWidgets.QHBoxLayout()
        button_row.addWidget(apply_button)
        button_row.addWidget(rotate_button)
        button_row.addWidget(delete_button)

        layout = QtWidgets.QVBoxLayout(page)
        layout.addLayout(form)
        layout.addLayout(button_row)
        layout.addStretch(1)
        return page

    def _build_pipe_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout()
        self.pipe_original_id = ""
        self.pipe_id_label = QtWidgets.QLabel()
        self.pipe_label_edit = QtWidgets.QLineEdit()
        self.pipe_x1 = self._double_spin(-10000, 10000, 1)
        self.pipe_y1 = self._double_spin(-10000, 10000, 1)
        self.pipe_x2 = self._double_spin(-10000, 10000, 1)
        self.pipe_y2 = self._double_spin(-10000, 10000, 1)
        self.pipe_thickness = self._double_spin(1, 100, 1)

        form.addRow("ID", self.pipe_id_label)
        form.addRow("Label", self.pipe_label_edit)
        form.addRow("Start X", self.pipe_x1)
        form.addRow("Start Y", self.pipe_y1)
        form.addRow("End X", self.pipe_x2)
        form.addRow("End Y", self.pipe_y2)
        form.addRow("Thickness", self.pipe_thickness)

        apply_button = QtWidgets.QPushButton("Apply")
        delete_button = QtWidgets.QPushButton("Delete")
        rotate_button = QtWidgets.QPushButton("Rotate +90°")
        apply_button.clicked.connect(self._emit_pipe_update)
        delete_button.clicked.connect(self.delete_requested.emit)
        rotate_button.clicked.connect(lambda: self.rotate_requested.emit(90.0))

        button_row = QtWidgets.QHBoxLayout()
        button_row.addWidget(apply_button)
        button_row.addWidget(rotate_button)
        button_row.addWidget(delete_button)

        layout = QtWidgets.QVBoxLayout(page)
        layout.addLayout(form)
        layout.addLayout(button_row)
        layout.addStretch(1)
        return page

    def _double_spin(self, minimum: float, maximum: float, decimals: int) -> QtWidgets.QDoubleSpinBox:
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setSingleStep(5.0)
        return spin

    def _populate_type_combo(self, current_type: str) -> None:
        self.element_type_combo.clear()
        if self.panel_config is None:
            return
        for type_id, spec in self.panel_config.valve_types.items():
            self.element_type_combo.addItem(f"{spec.display_name} [{spec.shape}]", type_id)
        index = self.element_type_combo.findData(current_type)
        if index >= 0:
            self.element_type_combo.setCurrentIndex(index)

    def _populate_relay_combo(self, actuator_id: str | None) -> None:
        self.relay_combo.clear()
        self.relay_combo.addItem("None / unbound", None)
        device_id = str(self.device_combo.currentData() or "controller")
        actuator = self.actuator_registry.maybe_get(actuator_id)
        current_relay = (
            actuator.relay_number
            if actuator is not None and actuator.device_id == device_id
            else None
        )
        usage = self.actuator_registry.relay_usage(device_id)
        for relay in range(1, self.actuator_registry.relay_count + 1):
            owners = [
                owner.actuator_id
                for owner in usage.get((device_id, relay), [])
                if owner.actuator_id != actuator_id
            ]
            if current_relay == relay:
                label = f"Relay {relay} — current"
            elif owners:
                label = f"Relay {relay} — used by {', '.join(owners)}"
            else:
                label = f"Relay {relay} — available"
            self.relay_combo.addItem(label, relay)
        index = self.relay_combo.findData(current_relay)
        if index >= 0:
            self.relay_combo.setCurrentIndex(index)

    def _refresh_relay_combo_for_device(self) -> None:
        if self._loading:
            return
        self._populate_relay_combo(self.actuator_id_edit.text().strip() or None)

    def _refresh_actuator_binding_fields(self) -> None:
        if self._loading:
            return
        actuator_id = self.actuator_id_edit.text().strip()
        actuator = self.actuator_registry.maybe_get(actuator_id)
        if actuator is not None:
            index = self.device_combo.findData(actuator.device_id)
            if index >= 0:
                self.device_combo.setCurrentIndex(index)
        self._populate_relay_combo(actuator_id or None)

    def _populate_element(self, element: ActuatedElementConfig) -> None:
        self.element_original_id = element.id
        self.element_id_edit.setText(element.id)
        self.element_label_edit.setText(element.label)
        self._populate_type_combo(element.element_type)
        actuator_id = element.actuator_id or element.id
        self.actuator_id_edit.setText(actuator_id)
        actuator = self.actuator_registry.maybe_get(actuator_id)
        if actuator is not None:
            device_index = self.device_combo.findData(actuator.device_id)
            if device_index >= 0:
                self.device_combo.setCurrentIndex(device_index)
        self._populate_relay_combo(actuator_id)
        self.element_x.setValue(element.center[0])
        self.element_y.setValue(element.center[1])
        self.element_w.setValue(element.size[0])
        self.element_h.setValue(element.size[1])
        self.element_rotation.setValue(element.rotation % 360.0)
        self.element_state.setChecked(element.initially_active)
        self.element_locked.setChecked(element.locked)
        self.element_enabled.setChecked(element.enabled)

    def _populate_pipe(self, pipe: PipeConfig) -> None:
        self.pipe_original_id = pipe.id
        self.pipe_id_label.setText(pipe.id)
        self.pipe_label_edit.setText(pipe.label)
        self.pipe_x1.setValue(pipe.start[0])
        self.pipe_y1.setValue(pipe.start[1])
        self.pipe_x2.setValue(pipe.end[0])
        self.pipe_y2.setValue(pipe.end[1])
        self.pipe_thickness.setValue(pipe.thickness)

    def _emit_element_update(self) -> None:
        if self.panel_config is None or not self.element_original_id:
            return
        element_id = self.element_id_edit.text().strip()
        if not element_id:
            QtWidgets.QMessageBox.warning(self, "Invalid element", "Element ID cannot be empty.")
            return
        duplicate = any(element.id == element_id and element.id != self.element_original_id for element in self.panel_config.elements)
        if duplicate:
            QtWidgets.QMessageBox.warning(self, "Duplicate element", f"Element ID {element_id!r} already exists.")
            return
        actuator_id = self.actuator_id_edit.text().strip()
        if not actuator_id:
            QtWidgets.QMessageBox.warning(self, "Invalid actuator", "Actuator ID cannot be empty.")
            return
        for element in self.panel_config.elements:
            if element.id != self.element_original_id and element.actuator_id == actuator_id:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Actuator already used",
                    f"Actuator {actuator_id!r} is already referenced by {element.id!r}.",
                )
                return
        device_id = str(self.device_combo.currentData() or "controller")
        relay = self.relay_combo.currentData()
        existing_actuator = self.actuator_registry.maybe_get(actuator_id)
        if (
            existing_actuator is not None
            and existing_actuator.kind in {"crusher_solenoid", "crusher"}
            and self.panel_config.element_by_id(self.element_original_id).actuator_id != actuator_id
        ):
            QtWidgets.QMessageBox.warning(
                self,
                "Actuator belongs to crusher hardware",
                f"Actuator {actuator_id!r} is reserved for crusher control.",
            )
            return

        candidate = ActuatorDefinition(
            actuator_id=actuator_id,
            label=self.element_label_edit.text().strip() or element_id,
            kind=str(self.element_type_combo.currentData()),
            device_id=device_id,
            relay_number=relay,
            enabled=self.element_enabled.isChecked(),
            default_active=self.element_state.isChecked(),
            metadata=(dict(existing_actuator.metadata) if existing_actuator else {}),
        )
        try:
            self.actuator_registry.upsert(candidate)
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Invalid actuator binding", str(exc))
            return
        original_metadata = dict(self.panel_config.element_by_id(self.element_original_id).metadata)
        original_metadata.pop("_legacy_relay_number", None)
        replacement = ActuatedElementConfig(
            id=element_id,
            label=self.element_label_edit.text().strip() or element_id,
            element_type=str(self.element_type_combo.currentData()),
            center=(float(self.element_x.value()), float(self.element_y.value())),
            size=(float(self.element_w.value()), float(self.element_h.value())),
            rotation=float(self.element_rotation.value()),
            actuator_id=actuator_id,
            initially_active=self.element_state.isChecked(),
            enabled=self.element_enabled.isChecked(),
            locked=self.element_locked.isChecked(),
            metadata=original_metadata,
        )
        self.element_changed.emit(self.element_original_id, replacement)

    def _emit_pipe_update(self) -> None:
        if self.panel_config is None or not self.pipe_original_id:
            return
        original = self.panel_config.pipe_by_id(self.pipe_original_id)
        replacement = PipeConfig(
            id=original.id,
            label=self.pipe_label_edit.text().strip(),
            start=(float(self.pipe_x1.value()), float(self.pipe_y1.value())),
            end=(float(self.pipe_x2.value()), float(self.pipe_y2.value())),
            thickness=float(self.pipe_thickness.value()),
            metadata=dict(original.metadata),
        )
        self.pipe_changed.emit(self.pipe_original_id, replacement)
