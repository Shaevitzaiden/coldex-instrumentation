from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml

from .models import DashboardConfig, DeviceDefinition, SensorDefinition


def load_device_definitions(path: str | Path) -> dict[str, DeviceDefinition]:
    """Load independently managed device definitions from YAML."""

    path = Path(path)
    if not path.exists():
        return {
            "controller": DeviceDefinition(
                device_id="controller",
                communicator_key="controller",
                command_target=True,
            )
        }
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    devices = raw.get("devices", raw)
    return {
        str(device_id): DeviceDefinition.from_dict(str(device_id), data or {})
        for device_id, data in devices.items()
    }


def save_device_definitions(definitions: Iterable[DeviceDefinition], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"devices": {definition.device_id: definition.to_dict() for definition in definitions}}
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def load_sensor_definitions(path: str | Path) -> dict[str, SensorDefinition]:
    path = Path(path)
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sensors = raw.get("sensors", raw)
    definitions: dict[str, SensorDefinition] = {}
    for sensor_id, data in sensors.items():
        definition = SensorDefinition.from_dict(str(sensor_id), data or {})
        # New configs should use globally qualified IDs.  For old short IDs,
        # create a qualified runtime ID while still accepting the old YAML.
        runtime_id = definition.sensor_id
        if "." not in runtime_id:
            runtime_id = f"{definition.source_device}.{definition.source_channel}"
            definition = SensorDefinition(
                sensor_id=runtime_id,
                label=definition.label,
                source_device=definition.source_device,
                source_channel=definition.source_channel,
                unit=definition.unit,
                expected_sampling_hz=definition.expected_sampling_hz,
                description=definition.description,
                enabled=definition.enabled,
                default_log=definition.default_log,
                metadata=dict(definition.metadata),
            )
        definitions[runtime_id] = definition
    return definitions


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
    """Return the standard 8-column x 3-row equipment dashboard.

    Logical placement:
        * pneumatic valve panel: left 4 columns x upper 2 rows
        * crusher controls: left 4 columns x bottom row
        * live sensor plots: middle 2 columns x upper 2 rows
        * sensor readout cards: middle 2 columns x bottom row
        * session recording: right 2 columns x all 3 rows

    The eight equal-stretch logical columns make the 4/2/2 width allocation
    explicit and predictable.  Detached/floating panels do not occupy grid
    cells and therefore do not disturb these proportions.
    """

    from .models import DashboardTileConfig

    return DashboardConfig(
        rows=3,
        columns=8,
        row_stretches=[1, 1, 1],
        column_stretches=[1, 1, 1, 1, 1, 1, 1, 1],
        dock_layout_version="fixed_grid_v4_8col_spawn_floating",
        tiles=[
            DashboardTileConfig(
                tile_id="valve_panel_main",
                tile_type="valve_panel",
                title="Pneumatic Valve Panel",
                row=0,
                column=0,
                row_span=2,
                column_span=4,
                removable=False,
            ),
            DashboardTileConfig(
                tile_id="plot_main",
                tile_type="live_plot",
                title="Live Sensor Plots",
                row=0,
                column=4,
                row_span=2,
                column_span=2,
                config={"channels": [], "history_seconds": 30.0, "group_by_unit": True},
            ),
            DashboardTileConfig(
                tile_id="crushers_main",
                tile_type="crusher_control",
                title="Ice Crushers",
                row=2,
                column=0,
                row_span=1,
                column_span=4,
                removable=True,
                config={
                    "initialize_retracted": True,
                    "crushers": [
                        {"id": f"crusher_{index}", "label": f"Crusher {index}", "actuator_id": f"crusher_{index}"}
                        for index in range(1, 5)
                    ],
                },
            ),
            DashboardTileConfig(
                tile_id="sensor_cards_main",
                tile_type="sensor_readout",
                title="Sensor Values",
                row=2,
                column=4,
                row_span=1,
                column_span=2,
                removable=True,
                config={
                    "channels": [],
                    "columns": 2,
                    "default_decimals": 1,
                    "value_font_size": 18,
                    "show_units": True,
                    "show_source": False,
                },
            ),
            DashboardTileConfig(
                tile_id="recording_session",
                tile_type="recording",
                title="Session Recording",
                row=0,
                column=6,
                row_span=3,
                column_span=2,
                removable=False,
            ),
        ],
    )
