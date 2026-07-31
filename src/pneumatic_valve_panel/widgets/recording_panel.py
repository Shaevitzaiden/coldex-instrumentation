from __future__ import annotations

from pathlib import Path

from PyQt5 import QtCore, QtWidgets

from ..data.models import SensorDefinition


class RecordingPanel(QtWidgets.QWidget):
    start_requested = QtCore.pyqtSignal(object)  # list[str]
    stop_requested = QtCore.pyqtSignal()
    snapshot_requested = QtCore.pyqtSignal()
    save_now_requested = QtCore.pyqtSignal()
    export_logs_requested = QtCore.pyqtSignal()
    save_close_requested = QtCore.pyqtSignal()
    base_directory_changed = QtCore.pyqtSignal(str)
    autosave_interval_changed = QtCore.pyqtSignal(int)

    def __init__(
        self,
        *,
        sensor_definitions: dict[str, SensorDefinition],
        base_directory: str | Path,
        autosave_interval_s: int = 30,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sensor_definitions = sensor_definitions

        self.directory_edit = QtWidgets.QLineEdit(str(base_directory))
        self.directory_button = QtWidgets.QPushButton("Browse…")
        self.directory_button.clicked.connect(self._browse_directory)
        directory_row = QtWidgets.QHBoxLayout()
        directory_row.addWidget(self.directory_edit, 1)
        directory_row.addWidget(self.directory_button)

        self.sensor_table = QtWidgets.QTableWidget(0, 4)
        self.sensor_table.setHorizontalHeaderLabels(["Log", "Sensor / source", "Unit", "Expected Hz"])
        self.sensor_table.verticalHeader().setVisible(False)
        self.sensor_table.horizontalHeader().setStretchLastSection(True)
        self.sensor_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        for sensor_id, definition in sensor_definitions.items():
            row = self.sensor_table.rowCount()
            self.sensor_table.insertRow(row)
            check = QtWidgets.QTableWidgetItem()
            check.setData(QtCore.Qt.UserRole, sensor_id)
            check.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable)
            check.setCheckState(QtCore.Qt.Checked if definition.default_log else QtCore.Qt.Unchecked)
            self.sensor_table.setItem(row, 0, check)
            label = QtWidgets.QTableWidgetItem(f"{definition.label} ({definition.sensor_id})")
            label.setToolTip(
                f"Device: {definition.source_device}\nLocal channel: {definition.source_channel}"
            )
            label.setFlags(QtCore.Qt.ItemIsEnabled)
            self.sensor_table.setItem(row, 1, label)
            unit = QtWidgets.QTableWidgetItem(definition.unit)
            unit.setFlags(QtCore.Qt.ItemIsEnabled)
            self.sensor_table.setItem(row, 2, unit)
            hz = "" if definition.expected_sampling_hz is None else f"{definition.expected_sampling_hz:g}"
            hz_item = QtWidgets.QTableWidgetItem(hz)
            hz_item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.sensor_table.setItem(row, 3, hz_item)
            if not definition.enabled:
                check.setFlags(QtCore.Qt.NoItemFlags)

        self.autosave_spin = QtWidgets.QSpinBox()
        self.autosave_spin.setRange(5, 3600)
        self.autosave_spin.setSuffix(" s")
        self.autosave_spin.setValue(autosave_interval_s)
        self.autosave_spin.valueChanged.connect(self.autosave_interval_changed)

        self.start_button = QtWidgets.QPushButton("Start Sensor Logging")
        self.stop_button = QtWidgets.QPushButton("Stop + Save")
        self.snapshot_button = QtWidgets.QPushButton("Save Snapshot")
        self.save_now_button = QtWidgets.QPushButton("Save Now")
        self.export_logs_button = QtWidgets.QPushButton("Export Logs…")
        self.save_close_button = QtWidgets.QPushButton("Save and Close")
        self.start_button.clicked.connect(lambda: self.start_requested.emit(self.selected_sensor_ids()))
        self.stop_button.clicked.connect(self.stop_requested)
        self.snapshot_button.clicked.connect(self.snapshot_requested)
        self.save_now_button.clicked.connect(self.save_now_requested)
        self.export_logs_button.clicked.connect(self.export_logs_requested)
        self.save_close_button.clicked.connect(self.save_close_requested)

        self.status_label = QtWidgets.QLabel("Sensor logging inactive")
        self.session_label = QtWidgets.QLabel("Session folder will be created on first save")
        self.session_label.setWordWrap(True)

        form = QtWidgets.QFormLayout()
        form.addRow("Session root", directory_row)
        form.addRow("Autosave every", self.autosave_spin)

        button_grid = QtWidgets.QGridLayout()
        button_grid.addWidget(self.start_button, 0, 0)
        button_grid.addWidget(self.stop_button, 0, 1)
        button_grid.addWidget(self.snapshot_button, 1, 0)
        button_grid.addWidget(self.save_now_button, 1, 1)
        button_grid.addWidget(self.export_logs_button, 2, 0)
        button_grid.addWidget(self.save_close_button, 2, 1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QtWidgets.QLabel("Sensors selected for per-channel recording"))
        layout.addWidget(self.sensor_table, 1)
        layout.addLayout(button_grid)
        layout.addWidget(self.status_label)
        layout.addWidget(self.session_label)
        self.set_recording_active(False)

    def selected_sensor_ids(self) -> list[str]:
        selected: list[str] = []
        for row in range(self.sensor_table.rowCount()):
            item = self.sensor_table.item(row, 0)
            if item and item.checkState() == QtCore.Qt.Checked:
                selected.append(str(item.data(QtCore.Qt.UserRole)))
        return selected

    @QtCore.pyqtSlot(bool)
    def set_recording_active(self, active: bool) -> None:
        self.start_button.setEnabled(not active)
        self.stop_button.setEnabled(active)
        self.sensor_table.setEnabled(not active)
        self.directory_edit.setEnabled(not active)
        self.directory_button.setEnabled(not active)
        self.status_label.setText("Sensor logging ACTIVE" if active else "Sensor logging inactive")

    @QtCore.pyqtSlot(str)
    def set_session_directory(self, directory: str) -> None:
        self.session_label.setText(f"Session folder: {directory}")

    @QtCore.pyqtSlot(str)
    def show_message(self, message: str) -> None:
        self.status_label.setText(message)

    def _browse_directory(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select session root directory",
            self.directory_edit.text(),
        )
        if not directory:
            return
        self.directory_edit.setText(directory)
        self.base_directory_changed.emit(directory)
