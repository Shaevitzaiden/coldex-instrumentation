from __future__ import annotations

"""Combined live plot + current-value dashboard tile.

This tile is intended for a *family of comparable sensors*: several chamber
temperatures, several pressures, several strain channels, etc.  All configured
channels share one live y-axis, while the latest value for every channel is
shown in a compact readout strip above the plot.

Like the other GUI tiles, this class is deliberately ignorant of serial ports
and worker threads.  It consumes normalized ``SensorFrame`` objects from
``DataHub`` in the Qt GUI thread.
"""

import collections
import time
from dataclasses import dataclass
from typing import Any

from PyQt5 import QtCore, QtGui, QtWidgets

from ...data.data_hub import DataHub
from ...data.models import SensorDefinition, SensorFrame
from ...data.sensor_groups import sensor_group_label, validate_same_sensor_group
from .tile_base import TileWidget

try:
    import pyqtgraph as pg
except ImportError:  # pragma: no cover - lightweight Qt fallback remains usable
    pg = None


@dataclass(frozen=True)
class _ReadoutOptions:
    label: str
    unit: str
    decimals: int
    format_spec: str | None
    font_size: int


class _LatestValueBox(QtWidgets.QFrame):
    """One compact current-value display used above the live plot."""

    def __init__(
        self,
        *,
        sensor_id: str,
        source_device: str,
        options: _ReadoutOptions,
        show_units: bool,
        show_source: bool,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.options = options
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Plain)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(1)

        name = QtWidgets.QLabel(options.label)
        name.setAlignment(QtCore.Qt.AlignCenter)
        name_font = name.font()
        name_font.setBold(True)
        name.setFont(name_font)

        self.value_label = QtWidgets.QLabel("—")
        self.value_label.setAlignment(QtCore.Qt.AlignCenter)
        value_font = self.value_label.font()
        value_font.setPointSize(max(8, options.font_size))
        value_font.setBold(True)
        self.value_label.setFont(value_font)

        unit = QtWidgets.QLabel(options.unit if show_units else "")
        unit.setAlignment(QtCore.Qt.AlignCenter)
        unit.setVisible(bool(show_units and options.unit))

        source = QtWidgets.QLabel(source_device if show_source else "")
        source.setAlignment(QtCore.Qt.AlignCenter)
        source.setVisible(bool(show_source and source_device))

        layout.addWidget(name)
        layout.addWidget(self.value_label)
        layout.addWidget(unit)
        layout.addWidget(source)
        self.setToolTip(f"Sensor: {sensor_id}\nSource device: {source_device}")

    def set_value(self, value: float) -> None:
        try:
            if self.options.format_spec:
                text = format(float(value), self.options.format_spec)
            else:
                text = f"{float(value):.{max(0, self.options.decimals)}f}"
        except (TypeError, ValueError):
            text = f"{float(value):g}"
        self.value_label.setText(text)

    def set_stale(self, stale: bool) -> None:
        self.setEnabled(not stale)
        self.value_label.setToolTip(
            "No recent sample has been received for this sensor." if stale else ""
        )


class _FallbackCombinedPlot(QtWidgets.QWidget):
    """Dependency-free plot used only when pyqtgraph is unavailable."""

    def __init__(self, *, title: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = title
        self.series: dict[str, list[tuple[float, float]]] = {}
        self.setMinimumSize(240, 130)

    def set_series(self, series: dict[str, list[tuple[float, float]]]) -> None:
        self.series = series
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor("white"))
        painter.setPen(QtGui.QColor(70, 70, 70))
        painter.drawText(self.rect().adjusted(8, 2, -8, -2), QtCore.Qt.AlignTop, self.title)
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
        for index, values in enumerate(self.series.values()):
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


class SensorPlotReadoutTile(TileWidget):
    """Show one comparable sensor group as both curves and latest values.

    The tile performs a defensive runtime validation in addition to the config
    dialog's filtering.  Hand-edited YAML therefore cannot silently put
    incompatible pressure/temperature channels on one y-axis.
    """

    def __init__(
        self,
        *,
        tile_id: str,
        title: str,
        data_hub: DataHub,
        sensor_definitions: dict[str, SensorDefinition],
        channels: list[str] | None = None,
        history_seconds: float = 30.0,
        readout_columns: int = 3,
        default_decimals: int = 2,
        value_font_size: int = 20,
        show_units: bool = True,
        show_source: bool = False,
        stale_after_s: float = 0.0,
        display: dict[str, dict[str, Any]] | None = None,
        y_label: str | None = None,
        removable: bool = True,
    ) -> None:
        self.data_hub = data_hub
        self.sensor_definitions = sensor_definitions
        requested = list(channels or [])
        if not requested:
            raise ValueError("A plot + readout tile requires at least one sensor channel.")

        # Raises a useful error if the YAML contains mixed quantities/units.
        self.sensor_group = validate_same_sensor_group(requested, sensor_definitions)
        self.channels = requested
        self.history_seconds = max(1.0, float(history_seconds))
        self.readout_columns = max(1, int(readout_columns))
        self.default_decimals = max(0, int(default_decimals))
        self.value_font_size = max(8, int(value_font_size))
        self.show_units = bool(show_units)
        self.show_source = bool(show_source)
        self.stale_after_s = max(0.0, float(stale_after_s))
        self.display_overrides = dict(display or {})
        self.y_label = str(y_label or sensor_group_label(self.sensor_group))

        self.buffers: dict[str, collections.deque[tuple[float, float]]] = {
            sensor_id: collections.deque() for sensor_id in self.channels
        }
        self._cards: dict[str, _LatestValueBox] = {}
        self._last_update_monotonic: dict[str, float] = {}
        self.curves: dict[str, Any] = {}
        self._fallback_plot: _FallbackCombinedPlot | None = None

        content = self._build_content()
        super().__init__(tile_id=tile_id, title=title, child=content, removable=removable)

        # DataHub delivers normalized frames on the GUI thread.  The frame is a
        # broadcast, so these channels may simultaneously feed plots,
        # recorders, other readout tiles, and future automation consumers.
        self.data_hub.frame_received.connect(self.on_frame)
        self._populate_existing_values()

        self._redraw_timer = QtCore.QTimer(self)
        self._redraw_timer.timeout.connect(self.redraw)
        self._redraw_timer.start(50)

        self._freshness_timer = QtCore.QTimer(self)
        self._freshness_timer.timeout.connect(self._update_freshness)
        if self.stale_after_s > 0:
            interval_ms = max(250, min(1000, int(self.stale_after_s * 250)))
            self._freshness_timer.start(interval_ms)

    def _build_content(self) -> QtWidgets.QWidget:
        content = QtWidgets.QWidget()
        outer = QtWidgets.QVBoxLayout(content)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(5)

        # Current values occupy a compact strip above the plot.  The number of
        # columns is configurable so the same class works for two sensors or a
        # larger array of comparable channels.
        readouts = QtWidgets.QWidget()
        readout_grid = QtWidgets.QGridLayout(readouts)
        readout_grid.setContentsMargins(0, 0, 0, 0)
        readout_grid.setSpacing(4)
        for index, sensor_id in enumerate(self.channels):
            definition = self.sensor_definitions[sensor_id]
            card = _LatestValueBox(
                sensor_id=sensor_id,
                source_device=definition.source_device,
                options=self._options_for_sensor(sensor_id, definition),
                show_units=self.show_units,
                show_source=self.show_source,
            )
            self._cards[sensor_id] = card
            readout_grid.addWidget(
                card,
                index // self.readout_columns,
                index % self.readout_columns,
            )
        for column in range(self.readout_columns):
            readout_grid.setColumnStretch(column, 1)
        outer.addWidget(readouts, 0)

        if pg is not None:
            plot_widget = pg.PlotWidget()
            plot_widget.showGrid(x=True, y=True, alpha=0.25)
            plot_widget.addLegend()
            plot_widget.setLabel("bottom", "Time", units="s")
            plot_widget.setLabel("left", self.y_label, units=self.sensor_group.unit or None)
            for index, sensor_id in enumerate(self.channels):
                # intColor gives stable, visually distinct curves without
                # requiring a color configuration in dashboard.yaml.
                pen = pg.mkPen(pg.intColor(index, hues=max(1, len(self.channels))), width=2)
                self.curves[sensor_id] = plot_widget.plot(
                    name=self.sensor_definitions[sensor_id].label,
                    pen=pen,
                )
            outer.addWidget(plot_widget, 1)
        else:
            self._fallback_plot = _FallbackCombinedPlot(title=self.y_label)
            outer.addWidget(self._fallback_plot, 1)

        return content

    def _options_for_sensor(
        self,
        sensor_id: str,
        definition: SensorDefinition,
    ) -> _ReadoutOptions:
        metadata = definition.metadata or {}
        override = self.display_overrides.get(sensor_id, {}) or {}

        try:
            decimals = max(
                0,
                int(
                    override.get(
                        "decimals",
                        metadata.get("display_decimals", self.default_decimals),
                    )
                ),
            )
        except (TypeError, ValueError):
            decimals = self.default_decimals

        format_raw = override.get("format", metadata.get("display_format"))
        format_spec = str(format_raw).strip() if format_raw not in (None, "") else None

        try:
            font_size = max(8, int(override.get("font_size", self.value_font_size)))
        except (TypeError, ValueError):
            font_size = self.value_font_size

        return _ReadoutOptions(
            label=str(override.get("label", definition.label)),
            unit=str(override.get("unit", definition.unit)),
            decimals=decimals,
            format_spec=format_spec,
            font_size=font_size,
        )

    def _populate_existing_values(self) -> None:
        for sensor_id, card in self._cards.items():
            value = self.data_hub.latest_values.get(sensor_id)
            if value is not None:
                card.set_value(value)

    @QtCore.pyqtSlot(object)
    def on_frame(self, frame: SensorFrame) -> None:
        cutoff = frame.elapsed_s - self.history_seconds
        now = time.monotonic()

        for sensor_id in self.channels:
            if sensor_id not in frame.values:
                continue

            value = float(frame.values[sensor_id])
            buffer = self.buffers[sensor_id]
            buffer.append((frame.elapsed_s, value))
            while buffer and buffer[0][0] < cutoff:
                buffer.popleft()

            card = self._cards[sensor_id]
            card.set_value(value)
            card.set_stale(False)
            self._last_update_monotonic[sensor_id] = now

    def redraw(self) -> None:
        latest = max(
            (buffer[-1][0] for buffer in self.buffers.values() if buffer),
            default=0.0,
        )

        if pg is not None:
            for sensor_id, buffer in self.buffers.items():
                if not buffer:
                    continue
                self.curves[sensor_id].setData(
                    [point[0] - latest for point in buffer],
                    [point[1] for point in buffer],
                )
            return

        if self._fallback_plot is not None:
            self._fallback_plot.set_series(
                {
                    sensor_id: [(x - latest, y) for x, y in self.buffers[sensor_id]]
                    for sensor_id in self.channels
                }
            )

    def _update_freshness(self) -> None:
        if self.stale_after_s <= 0:
            return
        now = time.monotonic()
        for sensor_id, card in self._cards.items():
            last_update = self._last_update_monotonic.get(sensor_id)
            if last_update is None:
                continue
            card.set_stale((now - last_update) > self.stale_after_s)
