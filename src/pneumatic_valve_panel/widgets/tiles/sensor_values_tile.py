from __future__ import annotations

from PyQt5 import QtCore, QtWidgets

from ...data.data_hub import DataHub
from ...data.models import SensorDefinition, SensorFrame
from .tile_base import TileWidget


class SensorValuesTile(TileWidget):
    def __init__(
        self,
        *,
        tile_id: str,
        title: str,
        data_hub: DataHub,
        sensor_definitions: dict[str, SensorDefinition],
        channels: list[str] | None = None,
        removable: bool = True,
    ) -> None:
        self.sensor_definitions = sensor_definitions
        self.channels = channels or list(sensor_definitions)
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Sensor", "Value", "Unit"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self._row_by_channel: dict[str, int] = {}
        for channel in self.channels:
            if channel not in sensor_definitions:
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._row_by_channel[channel] = row
            definition = sensor_definitions[channel]
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(definition.label))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem("—"))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(definition.unit))
        super().__init__(tile_id=tile_id, title=title, child=self.table, removable=removable)
        data_hub.frame_received.connect(self.on_frame)

    @QtCore.pyqtSlot(object)
    def on_frame(self, frame: SensorFrame) -> None:
        for channel, value in frame.values.items():
            row = self._row_by_channel.get(channel)
            if row is not None:
                self.table.item(row, 1).setText(f"{value:.6g}")
