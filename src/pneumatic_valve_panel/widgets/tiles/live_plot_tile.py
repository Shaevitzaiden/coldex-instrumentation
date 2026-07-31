from __future__ import annotations

"""Multi-plot live sensor dashboard panel.

One tile may contain several vertically stacked plot axes.  Each axis can show
multiple channels, and those channels may originate from completely different
serial devices because all IDs are resolved through the central StreamHub/DataHub
path before reaching this widget.
"""

import collections
from dataclasses import dataclass
from typing import Any

from PyQt5 import QtCore, QtGui, QtWidgets

from ...data.data_hub import DataHub
from ...data.models import SensorDefinition, SensorFrame
from .tile_base import TileWidget

try:
    import pyqtgraph as pg
except ImportError:  # pragma: no cover - fallback for environments without pyqtgraph
    pg = None


@dataclass(frozen=True)
class PlotGroup:
    """Configuration for one axis inside the live-plot tile."""

    title: str
    channels: tuple[str, ...]
    y_label: str = "Value"
    unit: str = ""


class _FallbackPlot(QtWidgets.QWidget):
    """Small dependency-free plot used when pyqtgraph is unavailable."""

    def __init__(self, *, group: PlotGroup, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.group = group
        self.series: dict[str, list[tuple[float, float]]] = {}
        self.setMinimumSize(240, 110)

    def set_series(self, series: dict[str, list[tuple[float, float]]]) -> None:
        self.series = series
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor("white"))
        painter.setPen(QtGui.QColor(70, 70, 70))
        painter.drawText(self.rect().adjusted(8, 2, -8, -2), QtCore.Qt.AlignTop, self.group.title)
        area = self.rect().adjusted(40, 22, -10, -22)
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
        colors = [
            QtGui.QColor("#1976d2"),
            QtGui.QColor("#d32f2f"),
            QtGui.QColor("#388e3c"),
            QtGui.QColor("#7b1fa2"),
            QtGui.QColor("#f57c00"),
        ]
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
    """Buffered panel containing one or more independent live plot axes.

    Incoming frames only append to deques.  A timer redraws at a human-visible
    rate, decoupling a potentially fast producer stream from GUI rendering.
    """

    def __init__(
        self,
        *,
        tile_id: str,
        title: str,
        data_hub: DataHub,
        sensor_definitions: dict[str, SensorDefinition],
        channels: list[str] | None = None,
        plot_groups: list[dict[str, Any]] | None = None,
        group_by_unit: bool = True,
        history_seconds: float = 30.0,
        removable: bool = True,
    ) -> None:
        self.sensor_definitions = sensor_definitions
        requested_channels = [
            channel
            for channel in (channels or list(sensor_definitions))
            if channel in sensor_definitions and sensor_definitions[channel].enabled
        ]
        self.plot_groups = self._resolve_plot_groups(
            plot_groups=plot_groups,
            channels=requested_channels,
            group_by_unit=group_by_unit,
        )
        self.channels = sorted({channel for group in self.plot_groups for channel in group.channels})
        self.history_seconds = max(1.0, float(history_seconds))
        self.buffers: dict[str, collections.deque[tuple[float, float]]] = {
            channel: collections.deque() for channel in self.channels
        }

        self.curves: dict[str, Any] = {}
        self._fallback_plots: list[tuple[PlotGroup, _FallbackPlot]] = []
        content = self._build_plot_content()
        super().__init__(tile_id=tile_id, title=title, child=content, removable=removable)

        data_hub.frame_received.connect(self.on_frame)
        self._redraw_timer = QtCore.QTimer(self)
        self._redraw_timer.timeout.connect(self.redraw)
        self._redraw_timer.start(50)

    def _resolve_plot_groups(
        self,
        *,
        plot_groups: list[dict[str, Any]] | None,
        channels: list[str],
        group_by_unit: bool,
    ) -> list[PlotGroup]:
        """Normalize YAML groups or automatically create sensible axes."""

        resolved: list[PlotGroup] = []
        for index, raw_group in enumerate(plot_groups or []):
            group_channels = tuple(
                channel
                for channel in raw_group.get("channels", [])
                if channel in self.sensor_definitions and self.sensor_definitions[channel].enabled
            )
            if not group_channels:
                continue
            first_definition = self.sensor_definitions[group_channels[0]]
            resolved.append(
                PlotGroup(
                    title=str(raw_group.get("title", f"Plot {index + 1}")),
                    channels=group_channels,
                    y_label=str(raw_group.get("y_label", "Value")),
                    unit=str(raw_group.get("unit", first_definition.unit)),
                )
            )
        if resolved:
            return resolved

        if group_by_unit:
            # Different physical units generally should not share one y-axis.
            # This automatically produces separate pressure, flow, temperature,
            # etc. plots while still allowing several same-unit channels per plot.
            grouped: dict[str, list[str]] = collections.defaultdict(list)
            for channel in channels:
                grouped[self.sensor_definitions[channel].unit or "unitless"].append(channel)
            for unit, group_channels in grouped.items():
                labels = [self.sensor_definitions[channel].label for channel in group_channels]
                title = labels[0] if len(labels) == 1 else f"{unit or 'Sensor'} channels"
                resolved.append(
                    PlotGroup(
                        title=title,
                        channels=tuple(group_channels),
                        y_label="Value",
                        unit="" if unit == "unitless" else unit,
                    )
                )
        elif channels:
            resolved.append(PlotGroup(title="Sensors", channels=tuple(channels)))
        return resolved

    def _build_plot_content(self) -> QtWidgets.QWidget:
        if pg is not None:
            # GraphicsLayoutWidget is designed to hold multiple PlotItems in one
            # efficient OpenGL/Qt graphics scene.
            graphics = pg.GraphicsLayoutWidget()
            for row, group in enumerate(self.plot_groups):
                plot_item = graphics.addPlot(row=row, col=0, title=group.title)
                plot_item.showGrid(x=True, y=True, alpha=0.25)
                plot_item.addLegend()
                plot_item.setLabel("bottom", "Time", units="s")
                plot_item.setLabel("left", group.y_label, units=group.unit or None)
                for channel in group.channels:
                    self.curves[channel] = plot_item.plot(
                        name=self.sensor_definitions[channel].label
                    )
            return graphics

        # The fallback uses ordinary Qt widgets and one custom plot per group.
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        for group in self.plot_groups:
            fallback = _FallbackPlot(group=group)
            self._fallback_plots.append((group, fallback))
            layout.addWidget(fallback, 1)
        if not self.plot_groups:
            layout.addWidget(QtWidgets.QLabel("No sensor channels configured", alignment=QtCore.Qt.AlignCenter))
        return container

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
        latest = max((buffer[-1][0] for buffer in self.buffers.values() if buffer), default=0.0)
        if pg is not None:
            for channel, buffer in self.buffers.items():
                if not buffer:
                    continue
                self.curves[channel].setData(
                    [point[0] - latest for point in buffer],
                    [point[1] for point in buffer],
                )
            return

        for group, fallback in self._fallback_plots:
            fallback.set_series(
                {
                    channel: [(x - latest, y) for x, y in self.buffers[channel]]
                    for channel in group.channels
                }
            )
