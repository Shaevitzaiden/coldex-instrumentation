from __future__ import annotations

import collections

from PyQt5 import QtCore, QtGui, QtWidgets

from ...data.data_hub import DataHub
from ...data.models import SensorDefinition, SensorFrame
from .tile_base import TileWidget

try:
    import pyqtgraph as pg
except ImportError:  # pragma: no cover - fallback for environments without pyqtgraph
    pg = None


class _FallbackPlot(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.series: dict[str, list[tuple[float, float]]] = {}
        self.setMinimumSize(240, 140)

    def set_series(self, series: dict[str, list[tuple[float, float]]]) -> None:
        self.series = series
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor("white"))
        painter.setPen(QtGui.QColor(100, 100, 100))
        area = self.rect().adjusted(38, 10, -10, -25)
        painter.drawRect(area)
        all_points = [point for values in self.series.values() for point in values]
        if not all_points:
            painter.drawText(area, QtCore.Qt.AlignCenter, "Waiting for sensor data")
            return
        xs = [point[0] for point in all_points]
        ys = [point[1] for point in all_points]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        if xmax <= xmin:
            xmax = xmin + 1.0
        if ymax <= ymin:
            ymax = ymin + 1.0
        colors = [QtGui.QColor("#1976d2"), QtGui.QColor("#d32f2f"), QtGui.QColor("#388e3c"), QtGui.QColor("#7b1fa2")]
        for index, (_, values) in enumerate(self.series.items()):
            if len(values) < 2:
                continue
            path = QtGui.QPainterPath()
            for point_index, (x, y) in enumerate(values):
                px = area.left() + (x - xmin) / (xmax - xmin) * area.width()
                py = area.bottom() - (y - ymin) / (ymax - ymin) * area.height()
                if point_index == 0:
                    path.moveTo(px, py)
                else:
                    path.lineTo(px, py)
            painter.setPen(QtGui.QPen(colors[index % len(colors)], 1.5))
            painter.drawPath(path)


class LivePlotTile(TileWidget):
    """Buffered live plot. Incoming frames only append data; a timer redraws."""

    def __init__(
        self,
        *,
        tile_id: str,
        title: str,
        data_hub: DataHub,
        sensor_definitions: dict[str, SensorDefinition],
        channels: list[str] | None = None,
        history_seconds: float = 30.0,
        removable: bool = True,
    ) -> None:
        self.sensor_definitions = sensor_definitions
        self.channels = [channel for channel in (channels or list(sensor_definitions)) if channel in sensor_definitions]
        self.history_seconds = max(1.0, float(history_seconds))
        self.buffers: dict[str, collections.deque[tuple[float, float]]] = {
            channel: collections.deque() for channel in self.channels
        }

        if pg is not None:
            self.plot_widget = pg.PlotWidget()
            self.plot_widget.showGrid(x=True, y=True, alpha=0.25)
            self.plot_widget.addLegend()
            self.plot_widget.setLabel("bottom", "Time", units="s")
            self.curves = {
                channel: self.plot_widget.plot(name=sensor_definitions[channel].label)
                for channel in self.channels
            }
        else:
            self.plot_widget = _FallbackPlot()
            self.curves = {}

        super().__init__(tile_id=tile_id, title=title, child=self.plot_widget, removable=removable)
        data_hub.frame_received.connect(self.on_frame)
        self._redraw_timer = QtCore.QTimer(self)
        self._redraw_timer.timeout.connect(self.redraw)
        self._redraw_timer.start(50)

    @QtCore.pyqtSlot(object)
    def on_frame(self, frame: SensorFrame) -> None:
        cutoff = frame.elapsed_s - self.history_seconds
        for channel in self.channels:
            if channel not in frame.values:
                continue
            buffer = self.buffers[channel]
            buffer.append((frame.elapsed_s, float(frame.values[channel])))
            while buffer and buffer[0][0] < cutoff:
                buffer.popleft()

    def redraw(self) -> None:
        if pg is not None:
            latest = max((buffer[-1][0] for buffer in self.buffers.values() if buffer), default=0.0)
            for channel, buffer in self.buffers.items():
                if not buffer:
                    continue
                xs = [point[0] - latest for point in buffer]
                ys = [point[1] for point in buffer]
                self.curves[channel].setData(xs, ys)
        else:
            latest = max((buffer[-1][0] for buffer in self.buffers.values() if buffer), default=0.0)
            series = {
                channel: [(x - latest, y) for x, y in buffer]
                for channel, buffer in self.buffers.items()
            }
            self.plot_widget.set_series(series)
