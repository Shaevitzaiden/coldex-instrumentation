from __future__ import annotations

"""Shared, transport-neutral data models.

The application deliberately passes immutable dataclasses between producers and
consumers.  A device thread may create a :class:`SensorFrame`, the recorder may
write it to disk, the plotting bridge may forward it to Qt, and an automation
worker may inspect it—all without any component mutating the object underneath
another consumer.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


def utc_now_iso() -> str:
    """Return a timezone-aware UTC timestamp suitable for logs and CSV files."""

    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class DeviceDefinition:
    """Configuration for one independently managed hardware/serial device.

    ``communicator_key`` selects an object from the mapping passed to
    ``run_app(..., communicators={...})``.  The YAML intentionally stores only
    configuration—not live Python objects—so device drivers remain injectable.
    """

    device_id: str
    enabled: bool = True
    communicator_key: str = ""
    command_target: bool = False
    description: str = ""
    connection: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, device_id: str, data: Mapping[str, Any]) -> "DeviceDefinition":
        return cls(
            device_id=str(device_id),
            enabled=bool(data.get("enabled", True)),
            communicator_key=str(data.get("communicator_key", device_id)),
            command_target=bool(data.get("command_target", False)),
            description=str(data.get("description", "")),
            connection=dict(data.get("connection", {})),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "communicator_key": self.communicator_key or self.device_id,
            "command_target": self.command_target,
            "description": self.description,
            "connection": dict(self.connection),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SensorDefinition:
    """Configuration describing one globally addressable sensor channel.

    Sensor identifiers are globally qualified (for example,
    ``controller.pressure_supply``).  ``source_device`` and ``source_channel``
    tell the device layer how a local channel name from a packet maps to that
    global identifier.
    """

    sensor_id: str
    label: str
    source_device: str
    source_channel: str
    unit: str = ""
    expected_sampling_hz: float | None = None
    description: str = ""
    enabled: bool = True
    default_log: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, sensor_id: str, data: Mapping[str, Any]) -> "SensorDefinition":
        expected = data.get("expected_sampling_hz", data.get("sampling_frequency_hz"))

        # Backwards compatibility: an older config may contain a short ID such
        # as ``pressure_supply`` and no explicit source fields.  It is treated
        # as a channel on the controller device rather than rejected.
        inferred_device, separator, inferred_channel = str(sensor_id).partition(".")
        if not separator:
            inferred_device = str(data.get("source_device", "controller"))
            inferred_channel = str(data.get("source_channel", sensor_id))

        return cls(
            sensor_id=str(sensor_id),
            label=str(data.get("label", sensor_id)),
            source_device=str(data.get("source_device", inferred_device)),
            source_channel=str(data.get("source_channel", inferred_channel)),
            unit=str(data.get("unit", "")),
            expected_sampling_hz=float(expected) if expected is not None else None,
            description=str(data.get("description", "")),
            enabled=bool(data.get("enabled", True)),
            default_log=bool(data.get("default_log", False)),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "label": self.label,
            "source_device": self.source_device,
            "source_channel": self.source_channel,
            "unit": self.unit,
            "enabled": self.enabled,
            "default_log": self.default_log,
        }
        if self.expected_sampling_hz is not None:
            data["expected_sampling_hz"] = self.expected_sampling_hz
        if self.description:
            data["description"] = self.description
        if self.metadata:
            data["metadata"] = dict(self.metadata)
        return data


@dataclass(frozen=True)
class SensorSample:
    """One channel extracted from a synchronized :class:`SensorFrame`."""

    sensor_id: str
    source_id: str
    value: float
    elapsed_s: float
    timestamp_utc: str
    host_received_monotonic_ns: int
    device_timestamp: float | str | None = None
    sequence: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SensorFrame:
    """One synchronized multi-channel sample frame from a single device.

    Every entry in ``values`` shares the same acquisition/receipt timestamps.
    Values are normalized to globally qualified sensor IDs before the frame is
    published to the central stream hub.

    The first three fields retain the ordering used by the older v6 API so
    external code constructing ``SensorFrame(elapsed_s, timestamp, values)``
    remains source compatible.
    """

    elapsed_s: float
    timestamp_utc: str
    values: dict[str, float]
    source_id: str = "controller"
    host_received_monotonic_ns: int = 0
    device_timestamp: float | str | None = None
    sequence: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def samples(self) -> tuple[SensorSample, ...]:
        """Return immutable per-channel samples without losing frame timing."""

        return tuple(
            SensorSample(
                sensor_id=sensor_id,
                source_id=self.source_id,
                value=float(value),
                elapsed_s=self.elapsed_s,
                timestamp_utc=self.timestamp_utc,
                host_received_monotonic_ns=self.host_received_monotonic_ns,
                device_timestamp=self.device_timestamp,
                sequence=self.sequence,
                metadata=dict(self.metadata),
            )
            for sensor_id, value in self.values.items()
        )


@dataclass(frozen=True)
class DeviceCommand:
    """Addressed command routed to exactly one device worker."""

    device_id: str
    command_type: str
    payload: dict[str, Any]
    origin: str = "application"
    command_id: str | None = None
    created_monotonic_ns: int = 0


@dataclass(frozen=True)
class CommandResult:
    """Result published after a device worker executes a command."""

    device_id: str
    command_type: str
    success: bool
    message: str
    payload: dict[str, Any] = field(default_factory=dict)
    command_id: str | None = None


@dataclass(frozen=True)
class DeviceStatus:
    """Connection/status update for one managed device."""

    device_id: str
    connected: bool
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LogEvent:
    timestamp_utc: str
    elapsed_s: float
    level: str
    source: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class DashboardTileConfig:
    tile_id: str
    tile_type: str
    title: str
    row: int
    column: int
    row_span: int = 1
    column_span: int = 1
    removable: bool = True
    floating: bool = False
    floating_geometry: list[int] | None = None
    config: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DashboardTileConfig":
        return cls(
            tile_id=str(data["id"]),
            tile_type=str(data.get("type", "log")),
            title=str(data.get("title", data.get("id", "Tile"))),
            row=int(data.get("row", 0)),
            column=int(data.get("column", data.get("col", 0))),
            row_span=max(1, int(data.get("row_span", 1))),
            column_span=max(1, int(data.get("column_span", data.get("col_span", 1)))),
            removable=bool(data.get("removable", True)),
            floating=bool(data.get("floating", False)),
            floating_geometry=(
                [int(v) for v in data.get("floating_geometry", [])[:4]]
                if data.get("floating_geometry")
                else None
            ),
            config=dict(data.get("config", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        data = {
            "id": self.tile_id,
            "type": self.tile_type,
            "title": self.title,
            "row": self.row,
            "column": self.column,
            "row_span": self.row_span,
            "column_span": self.column_span,
            "removable": self.removable,
            "config": dict(self.config),
        }
        if self.floating:
            data["floating"] = True
            if self.floating_geometry:
                data["floating_geometry"] = list(self.floating_geometry[:4])
        return data


@dataclass
class DashboardConfig:
    rows: int = 2
    columns: int = 2
    row_stretches: list[int] = field(default_factory=lambda: [3, 1])
    column_stretches: list[int] = field(default_factory=lambda: [3, 2])
    tiles: list[DashboardTileConfig] = field(default_factory=list)
    schema_version: int = 1
    dock_state: str | None = None
    dock_layout_version: str = "fixed_grid_v1"

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DashboardConfig":
        dashboard = dict(data.get("dashboard", data))
        tiles = [DashboardTileConfig.from_dict(item) for item in dashboard.get("tiles", [])]
        rows = max(1, int(dashboard.get("rows", 2)))
        columns = max(1, int(dashboard.get("columns", 2)))
        row_stretches = [max(0, int(value)) for value in dashboard.get("row_stretches", [3, 1])]
        column_stretches = [max(0, int(value)) for value in dashboard.get("column_stretches", [3, 2])]
        if len(row_stretches) < rows:
            row_stretches.extend([1] * (rows - len(row_stretches)))
        if len(column_stretches) < columns:
            column_stretches.extend([1] * (columns - len(column_stretches)))
        return cls(
            rows=rows,
            columns=columns,
            row_stretches=row_stretches[:rows],
            column_stretches=column_stretches[:columns],
            tiles=tiles,
            schema_version=int(data.get("schema_version", dashboard.get("schema_version", 1))),
            dock_state=(
                str(dashboard.get("dock_state"))
                if dashboard.get("dock_state") is not None
                else (str(data.get("dock_state")) if data.get("dock_state") is not None else None)
            ),
            dock_layout_version=str(
                dashboard.get("dock_layout_version", data.get("dock_layout_version", "legacy"))
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        data = {
            "schema_version": self.schema_version,
            "dashboard": {
                "rows": self.rows,
                "columns": self.columns,
                "row_stretches": list(self.row_stretches),
                "column_stretches": list(self.column_stretches),
                "tiles": [tile.to_dict() for tile in self.tiles],
            },
        }
        data["dashboard"]["dock_layout_version"] = self.dock_layout_version
        if self.dock_state:
            data["dashboard"]["dock_state"] = self.dock_state
        return data

    def tile_by_id(self, tile_id: str) -> DashboardTileConfig:
        for tile in self.tiles:
            if tile.tile_id == tile_id:
                return tile
        raise KeyError(tile_id)

    def next_tile_id(self, prefix: str) -> str:
        existing = {tile.tile_id for tile in self.tiles}
        index = 1
        while f"{prefix}_{index:02d}" in existing:
            index += 1
        return f"{prefix}_{index:02d}"
