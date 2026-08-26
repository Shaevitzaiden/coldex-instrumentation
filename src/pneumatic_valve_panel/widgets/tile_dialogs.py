from __future__ import annotations

"""Dialogs used to add and configure fixed-grid dashboard panels.

The important design rule in this module is that the dialog edits only
``DashboardTileConfig``.  It does not construct widgets or subscribe to sensor
streams itself.  ``MainWindow`` later hands the resulting config to
``TileRegistry``, which creates the appropriate tile class.
"""

from PyQt5 import QtCore, QtWidgets

from ..data.models import DashboardTileConfig, SensorDefinition


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
        "temperature_monitor",  # legacy alias
    }

    READOUT_TILE_TYPES = {
        "sensor_readout",
        "temperature_monitor",  # legacy alias uses the same display controls
    }

    def __init__(
        self,
        *,
        sensor_definitions: dict[str, SensorDefinition],
        existing: DashboardTileConfig | None = None,
        default_tile_id: str = "tile_01",
        default_row: int = 0,
        default_column: int = 0,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sensor_definitions = sensor_definitions
        self.existing = existing
        self.setWindowTitle("Configure Dashboard Panel" if existing else "Add Dashboard Panel")
        self.resize(470, 610)

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

        # ------------------------------------------------------------------
        # Generic sensor-readout options
        # ------------------------------------------------------------------
        self.readout_columns_spin = QtWidgets.QSpinBox()
        self.readout_columns_spin.setRange(1, 8)
        self.readout_columns_spin.setValue(int(existing_config.get("columns", 2)))
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
        else:
            config = {"channels": channels}

        if tile_type == "live_plot":
            config["history_seconds"] = self.history_spin.value()
            config["group_by_unit"] = self.group_by_unit_check.isChecked()

            # Preserve explicit YAML plot groups when the channel selection has
            # not changed.  If channels change, automatic unit grouping creates
            # a valid replacement without leaving stale group references.
            if self.existing is not None:
                old_channels = list(self.existing.config.get("channels", []))
                if old_channels == channels and self.existing.config.get("plot_groups"):
                    config["plot_groups"] = list(self.existing.config["plot_groups"])

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
        plot_visible = tile_type == "live_plot"
        readout_visible = tile_type in self.READOUT_TILE_TYPES

        self.sensor_label.setVisible(sensors_visible)
        self.sensor_list.setVisible(sensors_visible)

        self.history_label.setVisible(plot_visible)
        self.history_spin.setVisible(plot_visible)
        self.plot_grouping_label.setVisible(plot_visible)
        self.group_by_unit_check.setVisible(plot_visible)

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
