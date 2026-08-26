from __future__ import annotations

"""Backward-compatible temperature readout tile.

``TemperatureMonitorTile`` existed briefly while the generic readout feature was
being developed.  It now subclasses :class:`SensorReadoutTile` so old dashboard
YAML using ``type: temperature_monitor`` continues to work, while new layouts
should normally use ``type: sensor_readout``.
"""

from typing import Any

from ...data.data_hub import DataHub
from ...data.models import SensorDefinition
from .sensor_readout_tile import SensorReadoutTile


class TemperatureMonitorTile(SensorReadoutTile):
    """Legacy alias with temperature-friendly display defaults."""

    def __init__(
        self,
        *,
        tile_id: str,
        title: str,
        data_hub: DataHub,
        sensor_definitions: dict[str, SensorDefinition],
        channels: list[str],
        columns: int = 1,
        default_decimals: int = 1,
        value_font_size: int = 24,
        show_units: bool = True,
        show_source: bool = False,
        stale_after_s: float = 0.0,
        display: dict[str, dict[str, Any]] | None = None,
        removable: bool = True,
    ) -> None:
        super().__init__(
            tile_id=tile_id,
            title=title,
            data_hub=data_hub,
            sensor_definitions=sensor_definitions,
            channels=channels,
            columns=columns,
            default_decimals=default_decimals,
            value_font_size=value_font_size,
            show_units=show_units,
            show_source=show_source,
            stale_after_s=stale_after_s,
            display=display,
            removable=removable,
        )
