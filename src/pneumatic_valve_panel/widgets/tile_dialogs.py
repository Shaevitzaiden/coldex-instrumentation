from __future__ import annotations

from PyQt5 import QtCore, QtWidgets

from ..data.models import DashboardTileConfig, SensorDefinition


class TileConfigDialog(QtWidgets.QDialog):
    """Add/configure dashboard tile geometry and tile-specific options."""

    def __init__(
        self,
        *,
        sensor_definitions: dict[str, SensorDefinition],
        existing: DashboardTileConfig | None = None,
        default_tile_id: str = "tile_01",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sensor_definitions = sensor_definitions
        self.existing = existing
        self.setWindowTitle("Configure Dashboard Panel" if existing else "Add Dashboard Panel")
        self.resize(430, 520)

        self.id_edit = QtWidgets.QLineEdit(existing.tile_id if existing else default_tile_id)
        self.id_edit.setEnabled(existing is None)
        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItem("Live sensor plot", "live_plot")
        self.type_combo.addItem("Terminal-style log", "log")
        self.type_combo.addItem("Latest sensor values", "sensor_values")
        if existing and existing.tile_type == "valve_panel":
            self.type_combo.insertItem(0, "Valve panel", "valve_panel")
        if existing and existing.tile_type == "recording":
            self.type_combo.insertItem(0, "Session recording", "recording")
        if existing:
            index = self.type_combo.findData(existing.tile_type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)
            self.type_combo.setEnabled(False)

        self.title_edit = QtWidgets.QLineEdit(existing.title if existing else "New Tile")
        self.row_spin = QtWidgets.QSpinBox()
        self.row_spin.setRange(0, 99)
        self.row_spin.setValue(existing.row if existing else 0)
        self.column_spin = QtWidgets.QSpinBox()
        self.column_spin.setRange(0, 99)
        self.column_spin.setValue(existing.column if existing else 0)
        self.row_span_spin = QtWidgets.QSpinBox()
        self.row_span_spin.setRange(1, 20)
        self.row_span_spin.setValue(existing.row_span if existing else 1)
        self.column_span_spin = QtWidgets.QSpinBox()
        self.column_span_spin.setRange(1, 20)
        self.column_span_spin.setValue(existing.column_span if existing else 1)
        self.history_spin = QtWidgets.QDoubleSpinBox()
        self.history_spin.setRange(1.0, 3600.0)
        self.history_spin.setSuffix(" s")
        self.history_spin.setValue(float((existing.config if existing else {}).get("history_seconds", 30.0)))
        self.group_by_unit_check = QtWidgets.QCheckBox("Create separate plot axes for different units")
        self.group_by_unit_check.setChecked(bool((existing.config if existing else {}).get("group_by_unit", True)))
        self.group_by_unit_check.setToolTip(
            "Pressure, flow, temperature, and other units are normally easier to read on separate y-axes."
        )

        self.sensor_list = QtWidgets.QListWidget()
        self.sensor_list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        existing_channels = set((existing.config if existing else {}).get("channels", []))
        for sensor_id, definition in sensor_definitions.items():
            item = QtWidgets.QListWidgetItem(f"{definition.label} ({sensor_id})")
            item.setData(QtCore.Qt.UserRole, sensor_id)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            checked = sensor_id in existing_channels or (not existing_channels and definition.enabled)
            item.setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
            self.sensor_list.addItem(item)

        form = QtWidgets.QFormLayout()
        form.addRow("Tile ID", self.id_edit)
        form.addRow("Tile type", self.type_combo)
        form.addRow("Title", self.title_edit)
        form.addRow("Row", self.row_spin)
        form.addRow("Column", self.column_spin)
        form.addRow("Row span", self.row_span_spin)
        form.addRow("Column span", self.column_span_spin)
        form.addRow("Plot history", self.history_spin)
        form.addRow("Plot grouping", self.group_by_unit_check)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        self.sensor_label = QtWidgets.QLabel("Sensors shown by this tile")
        layout.addWidget(self.sensor_label)
        layout.addWidget(self.sensor_list, 1)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.type_combo.currentIndexChanged.connect(self._update_type_fields)
        self._update_type_fields()

    def result_config(self) -> DashboardTileConfig:
        channels = []
        for index in range(self.sensor_list.count()):
            item = self.sensor_list.item(index)
            if item.checkState() == QtCore.Qt.Checked:
                channels.append(str(item.data(QtCore.Qt.UserRole)))
        tile_type = str(self.type_combo.currentData())
        config = {} if tile_type in {"log", "valve_panel", "recording"} else {"channels": channels}
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
        if tile_type in {"live_plot", "sensor_values"} and not self.result_config().config.get("channels"):
            QtWidgets.QMessageBox.warning(self, "No sensors", "Select at least one sensor for this tile.")
            return
        self.accept()

    def _update_type_fields(self) -> None:
        tile_type = str(self.type_combo.currentData())
        sensors_visible = tile_type in {"live_plot", "sensor_values"}
        self.sensor_label.setVisible(sensors_visible)
        self.sensor_list.setVisible(sensors_visible)
        self.history_spin.setEnabled(tile_type == "live_plot")
        self.group_by_unit_check.setEnabled(tile_type == "live_plot")
