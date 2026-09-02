from __future__ import annotations

"""Dialogs used to add and configure fixed-grid dashboard panels.

The important design rule in this module is that the dialog edits only
``DashboardTileConfig``.  It does not construct widgets or subscribe to sensor
streams itself.  ``MainWindow`` later hands the resulting config to
``TileRegistry``, which creates the appropriate tile class.
"""

from PyQt5 import QtCore, QtWidgets

from ..actuators import ActuatorDefinition, ActuatorRegistry
from ..data.models import DashboardTileConfig, DeviceDefinition, SensorDefinition
from ..data.sensor_groups import (
    available_sensor_groups,
    sensor_group_key,
    sensor_group_label,
)


class TileConfigDialog(QtWidgets.QDialog):
    """Add/configure dashboard tile geometry and tile-specific options.

    Sensor-capable tiles all share the same channel picker.  A generic
    ``sensor_readout`` may display any enabled sensor.  The older
    ``temperature_monitor`` type is retained for backward compatibility and
    demonstrates how a tile-specific semantic filter can narrow that picker.
    """

    SENSOR_TILE_TYPES = {
        "live_plot",
        "sensor_values",
        "sensor_readout",
        "sensor_plot_readout",
        "temperature_monitor",  # legacy alias
    }

    READOUT_TILE_TYPES = {
        "sensor_readout",
        "sensor_plot_readout",
        "temperature_monitor",  # legacy alias uses the same display controls
    }

    def __init__(
        self,
        *,
        sensor_definitions: dict[str, SensorDefinition],
        actuator_registry: ActuatorRegistry | None = None,
        device_definitions: dict[str, DeviceDefinition] | None = None,
        existing: DashboardTileConfig | None = None,
        default_tile_id: str = "tile_01",
        default_row: int = 0,
        default_column: int = 0,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sensor_definitions = sensor_definitions
        self.actuator_registry = actuator_registry
        self.device_definitions = dict(device_definitions or {})
        self.existing = existing
        self.setWindowTitle("Configure Dashboard Panel" if existing else "Add Dashboard Panel")
        self.resize(520, 720)

        # ------------------------------------------------------------------
        # General tile identity / grid geometry
        # ------------------------------------------------------------------
        self.id_edit = QtWidgets.QLineEdit(existing.tile_id if existing else default_tile_id)
        self.id_edit.setEnabled(existing is None)

        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItem("Live sensor plot", "live_plot")
        self.type_combo.addItem("Terminal-style log", "log")
        self.type_combo.addItem("Latest sensor values (table)", "sensor_values")
        self.type_combo.addItem("Sensor readout cards", "sensor_readout")
        self.type_combo.addItem("Live plot + current values", "sensor_plot_readout")
        self.type_combo.addItem("Crusher controls", "crusher_control")
        self.type_combo.addItem("Device connectivity", "device_connectivity")

        # ``temperature_monitor`` is no longer offered for new tiles; the
        # generic sensor readout can do the same thing and much more.  If an old
        # dashboard already contains one, expose it so that tile is still
        # editable without silently changing its type.
        if existing and existing.tile_type == "temperature_monitor":
            self.type_combo.addItem("Temperature monitor (legacy)", "temperature_monitor")
        if existing and existing.tile_type == "valve_panel":
            self.type_combo.insertItem(0, "Valve panel", "valve_panel")
        if existing and existing.tile_type == "recording":
            self.type_combo.insertItem(0, "Session recording", "recording")

        if existing:
            index = self.type_combo.findData(existing.tile_type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)
            # Existing panels keep their type.  Reconfiguration changes title,
            # placement, selected channels, and type-specific options.
            self.type_combo.setEnabled(False)

        self.title_edit = QtWidgets.QLineEdit(existing.title if existing else "New Tile")

        self.row_spin = QtWidgets.QSpinBox()
        self.row_spin.setRange(0, 99)
        self.row_spin.setValue(existing.row if existing else max(0, int(default_row)))

        self.column_spin = QtWidgets.QSpinBox()
        self.column_spin.setRange(0, 99)
        self.column_spin.setValue(existing.column if existing else max(0, int(default_column)))

        self.row_span_spin = QtWidgets.QSpinBox()
        self.row_span_spin.setRange(1, 20)
        self.row_span_spin.setValue(existing.row_span if existing else 1)

        self.column_span_spin = QtWidgets.QSpinBox()
        self.column_span_spin.setRange(1, 20)
        self.column_span_spin.setValue(existing.column_span if existing else 1)

        existing_config = existing.config if existing else {}

        # ------------------------------------------------------------------
        # Live-plot-specific options
        # ------------------------------------------------------------------
        self.history_spin = QtWidgets.QDoubleSpinBox()
        self.history_spin.setRange(1.0, 3600.0)
        self.history_spin.setSuffix(" s")
        self.history_spin.setValue(float(existing_config.get("history_seconds", 30.0)))

        self.group_by_unit_check = QtWidgets.QCheckBox("Create separate plot axes for different units")
        self.group_by_unit_check.setChecked(bool(existing_config.get("group_by_unit", True)))
        self.group_by_unit_check.setToolTip(
            "Pressure, flow, temperature, and other units are normally easier to read on separate y-axes."
        )

        # ``sensor_plot_readout`` deliberately uses one y-axis.  The user
        # therefore chooses one compatible physical measurement group first
        # (for example Temperature [°C] or Pressure [kPa]); the sensor picker
        # below then exposes only channels from that group.
        self.sensor_group_combo = QtWidgets.QComboBox()
        for group in available_sensor_groups(sensor_definitions.values()):
            self.sensor_group_combo.addItem(sensor_group_label(group), group)

        # When editing an existing combined tile, restore the group either from
        # explicit YAML quantity/unit fields or by inferring it from its first
        # configured channel.
        if existing and existing.tile_type == "sensor_plot_readout":
            desired_group = None
            configured_quantity = str(existing_config.get("quantity", "")).strip()
            configured_unit = str(existing_config.get("unit", "")).strip()
            if configured_quantity:
                for index in range(self.sensor_group_combo.count()):
                    candidate = self.sensor_group_combo.itemData(index)
                    if (
                        candidate.quantity == configured_quantity
                        and candidate.unit == configured_unit
                    ):
                        desired_group = candidate
                        break
            if desired_group is None:
                for sensor_id in existing_config.get("channels", []):
                    definition = sensor_definitions.get(sensor_id)
                    if definition is not None:
                        desired_group = sensor_group_key(definition)
                        break
            if desired_group is not None:
                for index in range(self.sensor_group_combo.count()):
                    if self.sensor_group_combo.itemData(index) == desired_group:
                        self.sensor_group_combo.setCurrentIndex(index)
                        break

        # ------------------------------------------------------------------
        # Generic sensor-readout options
        # ------------------------------------------------------------------
        self.readout_columns_spin = QtWidgets.QSpinBox()
        self.readout_columns_spin.setRange(1, 8)
        self.readout_columns_spin.setValue(
            int(existing_config.get("readout_columns", existing_config.get("columns", 2)))
        )
        self.readout_columns_spin.setToolTip("Number of numeric sensor cards per row.")

        self.readout_decimals_spin = QtWidgets.QSpinBox()
        self.readout_decimals_spin.setRange(0, 9)
        self.readout_decimals_spin.setValue(int(existing_config.get("default_decimals", 2)))
        self.readout_decimals_spin.setToolTip(
            "Default number of decimal places. Per-sensor YAML display overrides take precedence."
        )

        self.readout_font_spin = QtWidgets.QSpinBox()
        self.readout_font_spin.setRange(8, 72)
        self.readout_font_spin.setSuffix(" pt")
        self.readout_font_spin.setValue(int(existing_config.get("value_font_size", 24)))

        self.readout_show_units_check = QtWidgets.QCheckBox("Show units")
        self.readout_show_units_check.setChecked(bool(existing_config.get("show_units", True)))

        self.readout_show_source_check = QtWidgets.QCheckBox("Show source device")
        self.readout_show_source_check.setChecked(bool(existing_config.get("show_source", False)))

        self.readout_stale_spin = QtWidgets.QDoubleSpinBox()
        self.readout_stale_spin.setRange(0.0, 3600.0)
        self.readout_stale_spin.setDecimals(1)
        self.readout_stale_spin.setSuffix(" s")
        self.readout_stale_spin.setSpecialValueText("Disabled")
        self.readout_stale_spin.setValue(float(existing_config.get("stale_after_s", 0.0)))
        self.readout_stale_spin.setToolTip(
            "Gray a readout after this many seconds without a new sample. Set to 0 to disable."
        )

        # ------------------------------------------------------------------
        # Crusher-control-specific options
        # ------------------------------------------------------------------
        # Crusher tiles reference logical actuator IDs.  Device/relay controls
        # below edit the same central registry used by the pneumatic element
        # editor, so there is exactly one authoritative binding per output.
        self.crusher_initialize_check = QtWidgets.QCheckBox(
            "Power/retract all crushers when this panel starts"
        )
        self.crusher_initialize_check.setChecked(
            bool(existing_config.get("initialize_retracted", True))
        )

        configured_crushers = list(existing_config.get("crushers", []))
        self.crusher_rows: list[tuple[
            QtWidgets.QWidget, QtWidgets.QLineEdit, QtWidgets.QLineEdit,
            QtWidgets.QComboBox, QtWidgets.QSpinBox
        ]] = []
        for index in range(1, 5):
            configured = (
                dict(configured_crushers[index - 1])
                if index - 1 < len(configured_crushers) else {}
            )
            crusher_id = str(configured.get("id", f"crusher_{index}"))
            actuator_id = str(configured.get("actuator_id", crusher_id))
            label_edit = QtWidgets.QLineEdit(str(configured.get("label", f"Crusher {index}")))
            actuator_edit = QtWidgets.QLineEdit(actuator_id)
            actuator_edit.setToolTip("Logical actuator ID stored in actuators.yaml")

            device_combo = QtWidgets.QComboBox()
            for device_id, definition in self.device_definitions.items():
                if definition.enabled:
                    device_combo.addItem(device_id, device_id)
            if device_combo.count() == 0:
                device_combo.addItem("controller", "controller")

            relay_spin = QtWidgets.QSpinBox()
            relay_spin.setRange(0, self.actuator_registry.relay_count if self.actuator_registry else 24)
            relay_spin.setSpecialValueText("Unassigned")
            actuator = self.actuator_registry.maybe_get(actuator_id) if self.actuator_registry else None
            if actuator is not None:
                device_index = device_combo.findData(actuator.device_id)
                if device_index >= 0:
                    device_combo.setCurrentIndex(device_index)
                relay_spin.setValue(actuator.relay_number or 0)
            else:
                raw_relay = configured.get("relay_number")  # legacy dashboard migration
                relay_spin.setValue(int(raw_relay) if raw_relay not in (None, "") else 0)

            row_widget = QtWidgets.QWidget()
            row_layout = QtWidgets.QGridLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.addWidget(QtWidgets.QLabel("Label"), 0, 0)
            row_layout.addWidget(label_edit, 0, 1, 1, 3)
            row_layout.addWidget(QtWidgets.QLabel("Actuator"), 1, 0)
            row_layout.addWidget(actuator_edit, 1, 1, 1, 3)
            row_layout.addWidget(QtWidgets.QLabel("Device"), 2, 0)
            row_layout.addWidget(device_combo, 2, 1)
            row_layout.addWidget(QtWidgets.QLabel("Relay"), 2, 2)
            row_layout.addWidget(relay_spin, 2, 3)
            self.crusher_rows.append(
                (row_widget, label_edit, actuator_edit, device_combo, relay_spin)
            )

        # ------------------------------------------------------------------
        # Shared sensor channel picker
        # ------------------------------------------------------------------
        self.sensor_list = QtWidgets.QListWidget()
        self.sensor_list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.sensor_list.setAlternatingRowColors(True)

        existing_channels = set(existing_config.get("channels", []))
        for sensor_id, definition in sensor_definitions.items():
            rate = (
                f" · {definition.expected_sampling_hz:g} Hz"
                if definition.expected_sampling_hz is not None
                else ""
            )
            unit = f" [{definition.unit}]" if definition.unit else ""
            item = QtWidgets.QListWidgetItem(f"{definition.label}{unit}{rate}")

            # Store the actual globally qualified ID separately from the
            # human-readable display text.  Never parse IDs back out of labels.
            item.setData(QtCore.Qt.UserRole, sensor_id)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)

            checked = sensor_id in existing_channels or (
                existing is None and not existing_channels and definition.enabled
            )
            item.setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
            item.setToolTip(
                f"Sensor ID: {sensor_id}\n"
                f"Source device: {definition.source_device}\n"
                f"Source channel: {definition.source_channel}\n"
                f"Quantity: {definition.metadata.get('quantity', 'unspecified')}"
            )
            self.sensor_list.addItem(item)

        # ------------------------------------------------------------------
        # Form/layout construction
        # ------------------------------------------------------------------
        form = QtWidgets.QFormLayout()
        form.addRow("Tile ID", self.id_edit)
        form.addRow("Tile type", self.type_combo)
        form.addRow("Title", self.title_edit)
        form.addRow("Row", self.row_spin)
        form.addRow("Column", self.column_spin)
        form.addRow("Row span", self.row_span_spin)
        form.addRow("Column span", self.column_span_spin)

        self.history_label = QtWidgets.QLabel("Plot history")
        form.addRow(self.history_label, self.history_spin)
        self.plot_grouping_label = QtWidgets.QLabel("Plot grouping")
        form.addRow(self.plot_grouping_label, self.group_by_unit_check)
        self.sensor_group_label_widget = QtWidgets.QLabel("Measurement group")
        form.addRow(self.sensor_group_label_widget, self.sensor_group_combo)

        self.readout_columns_label = QtWidgets.QLabel("Readout columns")
        form.addRow(self.readout_columns_label, self.readout_columns_spin)
        self.readout_decimals_label = QtWidgets.QLabel("Default decimals")
        form.addRow(self.readout_decimals_label, self.readout_decimals_spin)
        self.readout_font_label = QtWidgets.QLabel("Value font")
        form.addRow(self.readout_font_label, self.readout_font_spin)
        self.readout_stale_label = QtWidgets.QLabel("Stale indication")
        form.addRow(self.readout_stale_label, self.readout_stale_spin)
        form.addRow("", self.readout_show_units_check)
        form.addRow("", self.readout_show_source_check)

        self.crusher_initialize_label = QtWidgets.QLabel("Startup state")
        form.addRow(self.crusher_initialize_label, self.crusher_initialize_check)
        self.crusher_row_labels: list[QtWidgets.QLabel] = []
        for index, (row_widget, _label, _actuator, _device, _relay) in enumerate(self.crusher_rows, start=1):
            row_label = QtWidgets.QLabel(f"Crusher {index}")
            self.crusher_row_labels.append(row_label)
            form.addRow(row_label, row_widget)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        self.sensor_label = QtWidgets.QLabel("Sensors shown by this panel")
        layout.addWidget(self.sensor_label)
        layout.addWidget(self.sensor_list, 1)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # One handler owns all type-dependent UI changes.  The previous partial
        # implementation connected to a nonexistent ``_on_type_changed`` method
        # and then called another nonexistent ``_update_type_ui`` method.
        self.type_combo.currentIndexChanged.connect(self._on_tile_type_changed)
        self.sensor_group_combo.currentIndexChanged.connect(self._filter_sensor_list)
        self._on_tile_type_changed()

    # ------------------------------------------------------------------
    # Result construction / validation
    # ------------------------------------------------------------------
    def result_config(self) -> DashboardTileConfig:
        """Build a clean DashboardTileConfig from the current dialog state."""

        tile_type = str(self.type_combo.currentData())
        channels = self._selected_sensor_ids()

        if tile_type in {"log", "valve_panel", "recording"}:
            config: dict = {}
        elif tile_type == "device_connectivity":
            # There are no basic dialog fields for connectivity-specific options
            # yet, but preserve advanced YAML such as ``devices`` or
            # ``rate_window_s`` when the tile is repositioned/reconfigured.
            config = dict(self.existing.config) if self.existing is not None else {}
        elif tile_type == "crusher_control":
            config = {
                "initialize_retracted": self.crusher_initialize_check.isChecked(),
                "crushers": [
                    {
                        "id": f"crusher_{index}",
                        "label": label_edit.text().strip() or f"Crusher {index}",
                        "actuator_id": actuator_edit.text().strip() or f"crusher_{index}",
                    }
                    for index, (_row, label_edit, actuator_edit, _device, _relay)
                    in enumerate(self.crusher_rows, start=1)
                ],
            }
        else:
            config = {"channels": channels}

        if tile_type in {"live_plot", "sensor_plot_readout"}:
            config["history_seconds"] = self.history_spin.value()

        if tile_type == "live_plot":
            config["group_by_unit"] = self.group_by_unit_check.isChecked()

            # Preserve explicit YAML plot groups when the channel selection has
            # not changed.  If channels change, automatic unit grouping creates
            # a valid replacement without leaving stale group references.
            if self.existing is not None:
                old_channels = list(self.existing.config.get("channels", []))
                if old_channels == channels and self.existing.config.get("plot_groups"):
                    config["plot_groups"] = list(self.existing.config["plot_groups"])

        if tile_type == "sensor_plot_readout":
            group = self.sensor_group_combo.currentData()
            if group is not None:
                config["quantity"] = group.quantity
                config["unit"] = group.unit
                config["y_label"] = sensor_group_label(group)

        if tile_type in self.READOUT_TILE_TYPES:
            config.update(
                {
                    "columns": self.readout_columns_spin.value(),
                    "default_decimals": self.readout_decimals_spin.value(),
                    "value_font_size": self.readout_font_spin.value(),
                    "show_units": self.readout_show_units_check.isChecked(),
                    "show_source": self.readout_show_source_check.isChecked(),
                    "stale_after_s": self.readout_stale_spin.value(),
                }
            )

            if tile_type == "sensor_plot_readout":
                # The combined tile calls this option ``readout_columns`` to
                # distinguish it from dashboard grid column spans.
                config["readout_columns"] = config.pop("columns")

            # ``display`` contains optional per-sensor YAML overrides such as
            # custom labels or formatting.  The dialog does not currently edit
            # these advanced options, but it must preserve them when a user
            # changes geometry or channel selection.
            if self.existing is not None and self.existing.config.get("display"):
                config["display"] = dict(self.existing.config["display"])

        return DashboardTileConfig(
            tile_id=self.id_edit.text().strip(),
            tile_type=tile_type,
            title=self.title_edit.text().strip() or "Tile",
            row=self.row_spin.value(),
            column=self.column_spin.value(),
            row_span=self.row_span_spin.value(),
            column_span=self.column_span_spin.value(),
            removable=self.existing.removable if self.existing else True,
            config=config,
        )

    def _accept_if_valid(self) -> None:
        if not self.id_edit.text().strip():
            QtWidgets.QMessageBox.warning(self, "Missing ID", "Enter a tile ID.")
            return

        tile_type = str(self.type_combo.currentData())
        if tile_type in self.SENSOR_TILE_TYPES and not self._selected_sensor_ids():
            QtWidgets.QMessageBox.warning(
                self,
                "No sensors",
                "Select at least one enabled sensor for this panel.",
            )
            return

        if tile_type == "crusher_control":
            actuator_ids = [
                actuator_edit.text().strip()
                for _row, _label, actuator_edit, _device, _relay in self.crusher_rows
            ]
            if any(not actuator_id for actuator_id in actuator_ids):
                QtWidgets.QMessageBox.warning(self, "Missing actuator", "Each crusher needs an actuator ID.")
                return
            if len(set(actuator_ids)) != len(actuator_ids):
                QtWidgets.QMessageBox.warning(
                    self, "Duplicate crusher actuator", "Each crusher must reference a different actuator."
                )
                return
            if self.actuator_registry is not None:
                proposed = []
                for index, (_row, label_edit, actuator_edit, device_combo, relay_spin) in enumerate(self.crusher_rows, start=1):
                    actuator_id = actuator_edit.text().strip()
                    device_id = str(device_combo.currentData() or "controller")
                    relay = relay_spin.value() or None
                    label = label_edit.text().strip() or f"Crusher {index}"
                    existing_actuator = self.actuator_registry.maybe_get(actuator_id)
                    if (
                        existing_actuator is not None
                        and existing_actuator.kind not in {"crusher_solenoid", "crusher"}
                    ):
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Actuator already belongs to other hardware",
                            f"Actuator {actuator_id!r} is defined as {existing_actuator.kind!r}, "
                            "not a crusher actuator.",
                        )
                        return
                    if relay is None:
                        QtWidgets.QMessageBox.warning(
                            self, "Unassigned crusher actuator", f"Assign a relay to actuator {actuator_id}."
                        )
                        return
                    proposed.append((actuator_id, label, device_id, relay))

                # Apply all four definitions as one registry transaction.
                # Conflicts are validated against the final proposed map before
                # anything is changed, so swapping two crusher relays is legal
                # and a failed edit cannot leave half-created actuator entries.
                candidates = []
                for actuator_id, label, device_id, relay in proposed:
                    current = self.actuator_registry.maybe_get(actuator_id)
                    metadata = dict(current.metadata) if current is not None else {
                        "powered_state": "raised_retracted",
                        "unpowered_state": "lowered_extended",
                    }
                    candidates.append(
                        ActuatorDefinition(
                            actuator_id=actuator_id,
                            label=label,
                            kind="crusher_solenoid",
                            device_id=device_id,
                            relay_number=relay,
                            enabled=True,
                            default_active=True,
                            metadata=metadata,
                        )
                    )
                try:
                    self.actuator_registry.upsert_many(candidates)
                except ValueError as exc:
                    QtWidgets.QMessageBox.warning(self, "Invalid crusher relay binding", str(exc))
                    return


        self.accept()

    # ------------------------------------------------------------------
    # Type-dependent UI / filtering
    # ------------------------------------------------------------------
    def _on_tile_type_changed(self) -> None:
        """Refresh controls and sensor filtering after tile type changes."""

        self._update_type_fields()
        self._filter_sensor_list()

    def _update_type_fields(self) -> None:
        tile_type = str(self.type_combo.currentData())
        sensors_visible = tile_type in self.SENSOR_TILE_TYPES
        plot_visible = tile_type in {"live_plot", "sensor_plot_readout"}
        plot_grouping_visible = tile_type == "live_plot"
        measurement_group_visible = tile_type == "sensor_plot_readout"
        readout_visible = tile_type in self.READOUT_TILE_TYPES
        crusher_visible = tile_type == "crusher_control"

        self.sensor_label.setVisible(sensors_visible)
        self.sensor_list.setVisible(sensors_visible)

        self.history_label.setVisible(plot_visible)
        self.history_spin.setVisible(plot_visible)
        self.plot_grouping_label.setVisible(plot_grouping_visible)
        self.group_by_unit_check.setVisible(plot_grouping_visible)
        self.sensor_group_label_widget.setVisible(measurement_group_visible)
        self.sensor_group_combo.setVisible(measurement_group_visible)

        for widget in (
            self.readout_columns_label,
            self.readout_columns_spin,
            self.readout_decimals_label,
            self.readout_decimals_spin,
            self.readout_font_label,
            self.readout_font_spin,
            self.readout_stale_label,
            self.readout_stale_spin,
            self.readout_show_units_check,
            self.readout_show_source_check,
        ):
            widget.setVisible(readout_visible)

        for widget in (
            self.crusher_initialize_label,
            self.crusher_initialize_check,
            *self.crusher_row_labels,
            *(row_widget for row_widget, _label, _actuator, _device, _relay in self.crusher_rows),
        ):
            widget.setVisible(crusher_visible)

    def _sensor_allowed_for_tile(
        self,
        tile_type: str,
        definition: SensorDefinition,
    ) -> bool:
        """Return whether a sensor is meaningful/selectable for a tile type."""

        if not definition.enabled:
            return False

        # Generic sensor consumers can display any enabled numeric channel.
        if tile_type in {"live_plot", "sensor_values", "sensor_readout"}:
            return True

        # A combined plot/readout uses one y-axis, so only channels from the
        # explicitly selected measurement+unit group are valid.
        if tile_type == "sensor_plot_readout":
            selected_group = self.sensor_group_combo.currentData()
            return (
                selected_group is not None
                and sensor_group_key(definition) == selected_group
            )

        # Backward compatibility for old temperature-specific dashboard tiles.
        if tile_type == "temperature_monitor":
            quantity = str(definition.metadata.get("quantity", "")).strip().lower()
            if quantity:
                return quantity == "temperature"

            normalized_unit = definition.unit.strip().replace(" ", "").lower()
            return normalized_unit in {"°c", "c", "degc", "°f", "f", "degf", "k"}

        return False

    def _filter_sensor_list(self) -> None:
        """Hide channels that are invalid for the currently selected tile."""

        tile_type = str(self.type_combo.currentData())
        is_sensor_tile = tile_type in self.SENSOR_TILE_TYPES

        for row in range(self.sensor_list.count()):
            item = self.sensor_list.item(row)
            sensor_id = str(item.data(QtCore.Qt.UserRole))
            definition = self.sensor_definitions.get(sensor_id)
            allowed = bool(
                is_sensor_tile
                and definition is not None
                and self._sensor_allowed_for_tile(tile_type, definition)
            )

            item.setHidden(not allowed)

            # Only clear checked state when a *sensor* tile makes that channel
            # semantically invalid (for example an old temperature-only tile).
            # Switching briefly to a log tile should not destroy the user's
            # sensor selections if they switch back before pressing OK.
            if is_sensor_tile and not allowed:
                item.setCheckState(QtCore.Qt.Unchecked)

    def _selected_sensor_ids(self) -> list[str]:
        """Return checked, enabled, semantically valid global sensor IDs."""

        tile_type = str(self.type_combo.currentData())
        selected: list[str] = []

        for row in range(self.sensor_list.count()):
            item = self.sensor_list.item(row)
            if item.checkState() != QtCore.Qt.Checked:
                continue

            sensor_id = str(item.data(QtCore.Qt.UserRole))
            definition = self.sensor_definitions.get(sensor_id)
            if definition is None:
                continue
            if not self._sensor_allowed_for_tile(tile_type, definition):
                continue
            selected.append(sensor_id)

        # QListWidget rows are unique, but de-duplicating defensively keeps the
        # resulting YAML stable even if a future UI accidentally repeats rows.
        return list(dict.fromkeys(selected))
