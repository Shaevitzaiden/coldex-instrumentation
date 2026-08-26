from __future__ import annotations

"""Generic numeric sensor readout dashboard tile.

This module is intentionally GUI-only.  It does **not** know which serial port a
sensor came from and it never talks to :class:`DeviceManager` or
:class:`StreamHub` directly.  Device workers normalize all incoming data into
``SensorFrame`` objects, and ``QtDataBridge`` forwards a rate-limited copy of
those frames to ``DataHub`` in the Qt GUI thread.

That makes a readout tile a simple *consumer*:

    serial device(s) -> DeviceManager -> StreamHub -> QtDataBridge -> DataHub
                                                        |
                                                        +-> SensorReadoutTile

Because sensor IDs are globally qualified (``controller.temperature``,
``environment.temperature``, etc.), one tile may freely mix channels from
several hardware devices.
"""

import time
from dataclasses import dataclass
from typing import Any

from PyQt5 import QtCore, QtWidgets

from ...data.data_hub import DataHub
from ...data.models import SensorDefinition, SensorFrame
from .tile_base import TileWidget


@dataclass(frozen=True)
class _DisplayOptions:
    """Normalized display settings for one sensor card.

    ``dashboard.yaml`` can override these settings per channel using the
    ``display`` mapping on a ``sensor_readout`` tile.  Keeping the normalized
    settings in a small dataclass makes the actual update path very cheap.
    """

    label: str
    unit: str
    decimals: int
    format_spec: str | None
    font_size: int


class _SensorValueCard(QtWidgets.QFrame):
    """Small visual card containing sensor name, numeric value, and unit."""

    def __init__(
        self,
        *,
        sensor_id: str,
        source_device: str,
        options: _DisplayOptions,
        show_units: bool,
        show_source: bool,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.sensor_id = sensor_id
        self.options = options

        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Plain)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        self.name_label = QtWidgets.QLabel(options.label)
        self.name_label.setAlignment(QtCore.Qt.AlignCenter)
        name_font = self.name_label.font()
        name_font.setBold(True)
        self.name_label.setFont(name_font)

        # The large value label is the part updated for every matching frame.
        self.value_label = QtWidgets.QLabel("—")
        self.value_label.setAlignment(QtCore.Qt.AlignCenter)
        value_font = self.value_label.font()
        value_font.setPointSize(max(8, options.font_size))
        value_font.setBold(True)
        self.value_label.setFont(value_font)

        self.unit_label = QtWidgets.QLabel(options.unit if show_units else "")
        self.unit_label.setAlignment(QtCore.Qt.AlignCenter)
        self.unit_label.setVisible(bool(show_units and options.unit))

        self.source_label = QtWidgets.QLabel(source_device if show_source else "")
        self.source_label.setAlignment(QtCore.Qt.AlignCenter)
        self.source_label.setVisible(bool(show_source and source_device))

        layout.addWidget(self.name_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.unit_label)
        layout.addWidget(self.source_label)

        # The globally qualified ID is useful when several similarly named
        # sensors are displayed.  It is intentionally a tooltip rather than
        # permanent UI clutter.
        self.setToolTip(f"Sensor: {sensor_id}\nSource device: {source_device}")

    def set_value(self, value: float) -> None:
        """Format and display one numeric value.

        A custom Python format specification (for example ``.3f`` or ``.4g``)
        takes precedence over the decimal-count setting.  Invalid format specs
        are handled defensively so a typo in YAML cannot break the GUI.
        """

        try:
            if self.options.format_spec:
                text = format(float(value), self.options.format_spec)
            else:
                text = f"{float(value):.{max(0, self.options.decimals)}f}"
        except (TypeError, ValueError):
            text = f"{float(value):g}"
        self.value_label.setText(text)

    def set_stale(self, stale: bool) -> None:
        """Give stale values an obvious but non-alarming visual treatment."""

        self.setEnabled(not stale)
        if stale:
            self.value_label.setToolTip("No recent sample has been received for this sensor.")
        else:
            self.value_label.setToolTip("")


class SensorReadoutTile(TileWidget):
    """Display the latest numeric values for an arbitrary group of sensors.

    The tile is deliberately general-purpose.  A single instance can show:

    * temperature only,
    * pressure only,
    * all measurements from one subsystem, or
    * a mixed group of channels from several serial devices.

    ``channels`` controls *what* the tile subscribes to logically.  The tile
    still receives broadcast ``SensorFrame`` objects from ``DataHub`` and
    ignores values it was not configured to display.

    Parameters such as ``columns`` and ``display`` come directly from the
    tile's ``config`` section in ``dashboard.yaml``.  This allows multiple
    readout tiles to coexist with completely different contents and formatting.
    """

    def __init__(
        self,
        *,
        tile_id: str,
        title: str,
        data_hub: DataHub,
        sensor_definitions: dict[str, SensorDefinition],
        channels: list[str] | None = None,
        columns: int = 2,
        default_decimals: int = 2,
        value_font_size: int = 24,
        show_units: bool = True,
        show_source: bool = False,
        stale_after_s: float = 0.0,
        display: dict[str, dict[str, Any]] | None = None,
        removable: bool = True,
    ) -> None:
        self.data_hub = data_hub
        self.sensor_definitions = sensor_definitions

        # Filter the configured list once during construction.  Unknown or
        # disabled channels are ignored rather than crashing an old dashboard
        # file after sensors.yaml changes.
        requested = channels if channels is not None else list(sensor_definitions)
        self.channels = [
            sensor_id
            for sensor_id in requested
            if sensor_id in sensor_definitions and sensor_definitions[sensor_id].enabled
        ]

        self.columns = max(1, int(columns))
        self.default_decimals = max(0, int(default_decimals))
        self.value_font_size = max(8, int(value_font_size))
        self.show_units = bool(show_units)
        self.show_source = bool(show_source)
        self.stale_after_s = max(0.0, float(stale_after_s))
        self.display_overrides = dict(display or {})

        # Fast lookup tables used by on_frame().  Updating one frame should be
        # O(number of values in that frame), not O(number of widgets in app).
        self._cards: dict[str, _SensorValueCard] = {}
        self._last_update_monotonic: dict[str, float] = {}

        content = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(content)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setSpacing(6)

        for index, sensor_id in enumerate(self.channels):
            definition = sensor_definitions[sensor_id]
            options = self._options_for_sensor(sensor_id, definition)
            card = _SensorValueCard(
                sensor_id=sensor_id,
                source_device=definition.source_device,
                options=options,
                show_units=self.show_units,
                show_source=self.show_source,
            )
            self._cards[sensor_id] = card
            grid.addWidget(card, index // self.columns, index % self.columns)

        if not self.channels:
            empty_label = QtWidgets.QLabel("No enabled sensor channels configured")
            empty_label.setAlignment(QtCore.Qt.AlignCenter)
            grid.addWidget(empty_label, 0, 0)

        # Make every configured column share space evenly.  This gives a tidy
        # grouped readout whether the tile shows two channels or twenty.
        for column in range(self.columns):
            grid.setColumnStretch(column, 1)

        super().__init__(
            tile_id=tile_id,
            title=title,
            child=content,
            removable=removable,
        )

        # DataHub emits on the Qt GUI thread, making direct QLabel updates safe.
        self.data_hub.frame_received.connect(self.on_frame)

        # If the tile is added after acquisition has already started, populate
        # it immediately from the GUI-side latest-value cache rather than
        # waiting for the next sample from every device.
        self._populate_existing_values()

        # Optional stale-data indication.  stale_after_s <= 0 disables it.
        self._freshness_timer = QtCore.QTimer(self)
        self._freshness_timer.timeout.connect(self._update_freshness)
        if self.stale_after_s > 0:
            # There is no benefit to checking freshness faster than 4 Hz.
            interval_ms = max(250, min(1000, int(self.stale_after_s * 250)))
            self._freshness_timer.start(interval_ms)

    def _options_for_sensor(
        self,
        sensor_id: str,
        definition: SensorDefinition,
    ) -> _DisplayOptions:
        """Resolve defaults, sensor metadata, and tile-local YAML overrides.

        Precedence (highest last):

            built-in defaults
            -> SensorDefinition metadata
            -> this tile's dashboard.yaml ``display`` mapping

        This lets a sensor define a sensible project-wide display precision,
        while one particular tile can still choose a special label/format.
        """

        metadata = definition.metadata or {}
        override = self.display_overrides.get(sensor_id, {}) or {}

        label = str(override.get("label", definition.label))
        unit = str(override.get("unit", definition.unit))

        decimals_raw = override.get(
            "decimals",
            metadata.get("display_decimals", self.default_decimals),
        )
        try:
            decimals = max(0, int(decimals_raw))
        except (TypeError, ValueError):
            decimals = self.default_decimals

        format_spec_raw = override.get("format", metadata.get("display_format"))
        format_spec = str(format_spec_raw).strip() if format_spec_raw not in (None, "") else None

        font_size_raw = override.get("font_size", self.value_font_size)
        try:
            font_size = max(8, int(font_size_raw))
        except (TypeError, ValueError):
            font_size = self.value_font_size

        return _DisplayOptions(
            label=label,
            unit=unit,
            decimals=decimals,
            format_spec=format_spec,
            font_size=font_size,
        )

    def _populate_existing_values(self) -> None:
        """Populate values already known by DataHub when the tile is created."""

        for sensor_id, card in self._cards.items():
            value = self.data_hub.latest_values.get(sensor_id)
            if value is not None:
                card.set_value(value)

    @QtCore.pyqtSlot(object)
    def on_frame(self, frame: SensorFrame) -> None:
        """Update only displayed channels contained in one normalized frame."""

        now = time.monotonic()
        for sensor_id, value in frame.values.items():
            card = self._cards.get(sensor_id)
            if card is None:
                continue
            card.set_value(value)
            card.set_stale(False)
            self._last_update_monotonic[sensor_id] = now

    def _update_freshness(self) -> None:
        """Gray cards whose configured streams have stopped updating."""

        if self.stale_after_s <= 0:
            return
        now = time.monotonic()
        for sensor_id, card in self._cards.items():
            last_update = self._last_update_monotonic.get(sensor_id)
            # Do not mark a never-seen sensor stale immediately; its em dash is
            # already an unambiguous indication that no sample has arrived.
            if last_update is None:
                continue
            card.set_stale((now - last_update) > self.stale_after_s)
