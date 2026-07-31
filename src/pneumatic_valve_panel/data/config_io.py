from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml

from .models import DashboardConfig, SensorDefinition


def load_sensor_definitions(path: str | Path) -> dict[str, SensorDefinition]:
    path = Path(path)
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sensors = raw.get("sensors", raw)
    return {
        str(sensor_id): SensorDefinition.from_dict(str(sensor_id), data or {})
        for sensor_id, data in sensors.items()
    }


def save_sensor_definitions(definitions: Iterable[SensorDefinition], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"sensors": {definition.sensor_id: definition.to_dict() for definition in definitions}}
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def load_dashboard_config(path: str | Path) -> DashboardConfig:
    path = Path(path)
    if not path.exists():
        return default_dashboard_config()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    config = DashboardConfig.from_dict(raw)
    defaults = default_dashboard_config()
    if not any(tile.tile_type == "valve_panel" for tile in config.tiles):
        config.tiles.insert(0, defaults.tile_by_id("valve_panel_main"))
    if not any(tile.tile_type == "recording" for tile in config.tiles):
        config.tiles.append(defaults.tile_by_id("recording_session"))
    return config


def save_dashboard_config(config: DashboardConfig, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(config.to_dict(), sort_keys=False), encoding="utf-8")


def default_dashboard_config() -> DashboardConfig:
    from .models import DashboardTileConfig

    return DashboardConfig(
        rows=2,
        columns=2,
        row_stretches=[3, 1],
        column_stretches=[3, 2],
        dock_layout_version="fixed_grid_v1",
        tiles=[
            DashboardTileConfig(
                tile_id="valve_panel_main",
                tile_type="valve_panel",
                title="Pneumatic Valve Panel",
                row=0,
                column=0,
                removable=False,
            ),
            DashboardTileConfig(
                tile_id="plot_main",
                tile_type="live_plot",
                title="Live Sensor Plot",
                row=0,
                column=1,
                config={"channels": [], "history_seconds": 30.0},
            ),
            DashboardTileConfig(
                tile_id="log_main",
                tile_type="log",
                title="System Log",
                row=1,
                column=0,
            ),
            DashboardTileConfig(
                tile_id="recording_session",
                tile_type="recording",
                title="Session Recording",
                row=1,
                column=1,
                removable=False,
            ),
        ],
    )
