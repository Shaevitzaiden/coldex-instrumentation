from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


PointLike = Sequence[int | float]


def _as_point(value: PointLike, *, field_name: str) -> tuple[int, int]:
    if len(value) != 2:
        raise ValueError(f"{field_name} must contain exactly two values: [x, y]")
    return int(value[0]), int(value[1])


@dataclass
class AttachedLine:
    """Line segment drawn relative to a valve button center.

    Positive horizontal lengths draw to the right. Negative horizontal lengths
    draw to the left. Positive vertical lengths draw downward. Negative vertical
    lengths draw upward.
    """

    orientation: str
    length: int
    thickness: int = 12

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AttachedLine":
        orientation = str(data.get("orientation", "")).lower()
        if orientation not in {"h", "horizontal", "v", "vertical"}:
            raise ValueError(f"Unsupported attached line orientation: {orientation!r}")
        return cls(
            orientation="h" if orientation.startswith("h") else "v",
            length=int(data.get("length", 0)),
            thickness=int(data.get("thickness", 12)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "orientation": self.orientation,
            "length": self.length,
            "thickness": self.thickness,
        }


@dataclass
class PanelLine:
    """Standalone line segment drawn on the panel canvas."""

    orientation: str
    start: tuple[int, int]
    length: int
    thickness: int = 12

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PanelLine":
        orientation = str(data.get("orientation", "")).lower()
        if orientation not in {"h", "horizontal", "v", "vertical"}:
            raise ValueError(f"Unsupported panel line orientation: {orientation!r}")
        return cls(
            orientation="h" if orientation.startswith("h") else "v",
            start=_as_point(data.get("start", [0, 0]), field_name="line.start"),
            length=int(data.get("length", 0)),
            thickness=int(data.get("thickness", 12)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "orientation": self.orientation,
            "start": list(self.start),
            "length": self.length,
            "thickness": self.thickness,
        }


@dataclass
class ValveButtonConfig:
    """Configuration for one valve button on the panel."""

    id: str
    label: str
    center: tuple[int, int]
    command_id: Any = None
    radius: int | None = None
    initially_open: bool = False
    enabled: bool = True
    attached_lines: list[AttachedLine] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, default_radius: int) -> "ValveButtonConfig":
        valve_id = str(data["id"])
        return cls(
            id=valve_id,
            label=str(data.get("label", valve_id)),
            center=_as_point(data.get("center", [0, 0]), field_name=f"button {valve_id}.center"),
            command_id=data.get("command_id"),
            radius=int(data.get("radius", default_radius)),
            initially_open=bool(data.get("initially_open", False)),
            enabled=bool(data.get("enabled", True)),
            attached_lines=[AttachedLine.from_dict(item) for item in data.get("attached_lines", [])],
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "center": list(self.center),
            "command_id": self.command_id,
            "radius": self.radius,
            "initially_open": self.initially_open,
            "enabled": self.enabled,
        }
        if self.attached_lines:
            data["attached_lines"] = [line.to_dict() for line in self.attached_lines]
        if self.metadata:
            data["metadata"] = dict(self.metadata)
        return data


@dataclass
class PanelConfig:
    """Complete valve panel configuration."""

    title: str = "Pneumatic Valve Control"
    width: int = 1200
    height: int = 520
    button_radius: int = 52
    buttons: list[ValveButtonConfig] = field(default_factory=list)
    lines: list[PanelLine] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PanelConfig":
        panel_data = dict(data.get("panel", {}))
        default_radius = int(panel_data.get("button_radius", data.get("button_radius", 52)))
        return cls(
            title=str(panel_data.get("title", data.get("title", "Pneumatic Valve Control"))),
            width=int(panel_data.get("width", data.get("width", 1200))),
            height=int(panel_data.get("height", data.get("height", 520))),
            button_radius=default_radius,
            buttons=[
                ValveButtonConfig.from_dict(item, default_radius=default_radius)
                for item in data.get("buttons", [])
            ],
            lines=[PanelLine.from_dict(item) for item in data.get("lines", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "panel": {
                "title": self.title,
                "width": self.width,
                "height": self.height,
                "button_radius": self.button_radius,
            },
            "buttons": [button.to_dict() for button in self.buttons],
            "lines": [line.to_dict() for line in self.lines],
        }

    def button_by_id(self, valve_id: str) -> ValveButtonConfig:
        for button in self.buttons:
            if button.id == valve_id:
                return button
        raise KeyError(f"Unknown valve id: {valve_id}")
