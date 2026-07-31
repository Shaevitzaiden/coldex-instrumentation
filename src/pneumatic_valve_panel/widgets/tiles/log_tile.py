from __future__ import annotations

from PyQt5 import QtCore, QtGui, QtWidgets

from ...data.data_hub import DataHub
from ...data.models import LogEvent
from .tile_base import TileWidget


class LogTile(TileWidget):
    def __init__(self, *, tile_id: str, title: str, data_hub: DataHub, removable: bool = True) -> None:
        self.text = QtWidgets.QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.document().setMaximumBlockCount(5000)
        font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        self.text.setFont(font)
        super().__init__(tile_id=tile_id, title=title, child=self.text, removable=removable)
        data_hub.log_received.connect(self.append_event)

    @QtCore.pyqtSlot(object)
    def append_event(self, event: LogEvent) -> None:
        local_time = event.timestamp_utc.replace("T", " ")
        self.text.appendPlainText(
            f"{local_time} [{event.level:<7}] {event.source}: {event.message}"
        )
        scrollbar = self.text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
