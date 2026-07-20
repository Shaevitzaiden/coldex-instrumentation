from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


Number = int | float
PointLike = Sequence[Number]
SizeLike = Sequence[Number]


def _as_point(value: PointLike, *, field_name: str) -> tuple[float, float]:
    if len(value) != 2:
        raise ValueError(f"{field_name} must contain exactly two values: [x, y]")
    return float(value[0]), float(value[1])


def _as_size(value: SizeLike, *, field_name: str) -> tuple[float, float]:
    if len(value) != 2:
        raise ValueError(f"{field_name} must contain exactly two values: [width, height]")
    width = float(value[0])
    height = float(value[1])
    if width <= 0 or height <= 0:
        raise ValueError(f"{field_name} values must be positive")
    return width, height


@dataclass
class ValveTypeSpec:
    """Visual and semantic type used by configurable actuated elements.

    The ``type_id`` is what gets stored in the YAML. ``display_name`` is what the
    user sees in the Add/Edit dialog. ``shape`` controls how the element is drawn
    on the canvas.
    """

    type_id: str
    display_name: str
    shape: str = "circle"
    description: str = ""

    @classmethod
    def from_dict(cls, type_id: str, data: Mapping[str, Any]) -> "ValveTypeSpec":
        return cls(
            type_id=str(type_id),
            display_name=str(data.get("display_name", type_id.replace("_", " ").title())),
            shape=str(data.get("shape", "circle")),
            description=str(data.get("description", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "display_name": self.display_name,
            "shape": self.shape,
        }
        if self.description:
            data["description"] = self.description
        return data


@dataclass
class ActuatedElementConfig:
    """A clickable, serial-bound element on the pneumatic panel.

    This can represent a solenoid valve, a manual override relay, a pump, a
    regulator enable line, or any other actuated element. The GUI does not assume
    the hardware semantics; it only sends ``element_id``, ``state``, and
    ``relay_number`` through the controller/communicator boundary.
    """

    id: str
    label: str
    element_type: str
    center: tuple[float, float]
    size: tuple[float, float] = (56.0, 56.0)
    rotation: float = 0.0
    relay_number: int | None = None
    initially_active: bool = False
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        *,
        default_size: tuple[float, float],
        default_type: str,
    ) -> "ActuatedElementConfig":
        element_id = str(data["id"])
        relay_value = data.get("relay_number", data.get("relay", data.get("command_id")))
        relay_number = int(relay_value) if relay_value is not None else None
        return cls(
            id=element_id,
            label=str(data.get("label", element_id)),
            element_type=str(data.get("element_type", data.get("valve_type", default_type))),
            center=_as_point(data.get("center", [0, 0]), field_name=f"element {element_id}.center"),
            size=_as_size(data.get("size", default_size), field_name=f"element {element_id}.size"),
            rotation=float(data.get("rotation", 0.0)),
            relay_number=relay_number,
            initially_active=bool(data.get("initially_active", data.get("initially_open", False))),
            enabled=bool(data.get("enabled", True)),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "element_type": self.element_type,
            "center": [round(self.center[0], 3), round(self.center[1], 3)],
            "size": [round(self.size[0], 3), round(self.size[1], 3)],
            "rotation": round(self.rotation % 360.0, 3),
            "relay_number": self.relay_number,
            "initially_active": self.initially_active,
            "enabled": self.enabled,
        }
        if self.metadata:
            data["metadata"] = dict(self.metadata)
        return data


@dataclass
class PipeConfig:
    """A selectable pipe/plumbing segment drawn behind actuated elements."""

    id: str
    start: tuple[float, float]
    end: tuple[float, float]
    thickness: float = 18.0
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PipeConfig":
        pipe_id = str(data["id"])
        # Backward compatibility with old one-dimensional line entries.
        if "start" in data and "end" not in data and "length" in data:
            start = _as_point(data.get("start", [0, 0]), field_name=f"pipe {pipe_id}.start")
            length = float(data.get("length", 0))
            orientation = str(data.get("orientation", "h")).lower()
            if orientation.startswith("v"):
                end = (start[0], start[1] + length)
            else:
                end = (start[0] + length, start[1])
        else:
            start = _as_point(data.get("start", [0, 0]), field_name=f"pipe {pipe_id}.start")
            end = _as_point(data.get("end", [0, 0]), field_name=f"pipe {pipe_id}.end")

        return cls(
            id=pipe_id,
            start=start,
            end=end,
            thickness=float(data.get("thickness", 18.0)),
            label=str(data.get("label", "")),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "start": [round(self.start[0], 3), round(self.start[1], 3)],
            "end": [round(self.end[0], 3), round(self.end[1], 3)],
            "thickness": round(self.thickness, 3),
        }
        if self.label:
            data["label"] = self.label
        if self.metadata:
            data["metadata"] = dict(self.metadata)
        return data


@dataclass
class PanelConfig:
    """Complete scalable pneumatic panel configuration."""

    title: str = "Pneumatic Valve Control"
    design_width: float = 1200.0
    design_height: float = 520.0
    default_element_size: tuple[float, float] = (56.0, 56.0)
    background_color: str = "#f8f8f8"
    valve_types: dict[str, ValveTypeSpec] = field(default_factory=dict)
    elements: list[ActuatedElementConfig] = field(default_factory=list)
    pipes: list[PipeConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PanelConfig":
        panel_data = dict(data.get("panel", {}))
        design_width = float(panel_data.get("design_width", panel_data.get("width", data.get("width", 1200))))
        design_height = float(panel_data.get("design_height", panel_data.get("height", data.get("height", 520))))
        default_diameter = float(panel_data.get("button_radius", data.get("button_radius", 56)))
        default_size = _as_size(
            panel_data.get("default_element_size", [default_diameter, default_diameter]),
            field_name="panel.default_element_size",
        )

        raw_types = dict(data.get("valve_types", {}))
        if not raw_types:
            raw_types = default_valve_types_as_dict()
        valve_types = {
            str(type_id): ValveTypeSpec.from_dict(str(type_id), spec)
            for type_id, spec in raw_types.items()
        }
        default_type = next(iter(valve_types.keys()))

        # New schema uses ``elements``. Older barebones schema used ``buttons``.
        raw_elements = data.get("elements", data.get("buttons", []))
        elements = [
            ActuatedElementConfig.from_dict(item, default_size=default_size, default_type=default_type)
            for item in raw_elements
        ]

        raw_pipes = data.get("pipes", data.get("lines", []))
        pipes: list[PipeConfig] = []
        for index, item in enumerate(raw_pipes, start=1):
            item = dict(item)
            item.setdefault("id", f"pipe_{index:03d}")
            pipes.append(PipeConfig.from_dict(item))

        # Convert old attached_lines into standalone selectable pipes.
        next_pipe_index = len(pipes) + 1
        # The old schema stores attached line data in each button. That data is
        # not kept by ActuatedElementConfig, so inspect raw data directly.
        for raw_element in raw_elements:
            element_id = str(raw_element.get("id", "element"))
            center = _as_point(raw_element.get("center", [0, 0]), field_name=f"element {element_id}.center")
            for attached in raw_element.get("attached_lines", []):
                orientation = str(attached.get("orientation", "h")).lower()
                length = float(attached.get("length", 0))
                if orientation.startswith("v"):
                    end = (center[0], center[1] + length)
                else:
                    end = (center[0] + length, center[1])
                pipes.append(
                    PipeConfig(
                        id=f"pipe_{next_pipe_index:03d}",
                        start=center,
                        end=end,
                        thickness=float(attached.get("thickness", 18.0)),
                        metadata={"generated_from_attached_line": element_id},
                    )
                )
                next_pipe_index += 1

        return cls(
            title=str(panel_data.get("title", data.get("title", "Pneumatic Valve Control"))),
            design_width=design_width,
            design_height=design_height,
            default_element_size=default_size,
            background_color=str(panel_data.get("background_color", "#f8f8f8")),
            valve_types=valve_types,
            elements=elements,
            pipes=pipes,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "panel": {
                "title": self.title,
                "design_width": round(self.design_width, 3),
                "design_height": round(self.design_height, 3),
                "default_element_size": [
                    round(self.default_element_size[0], 3),
                    round(self.default_element_size[1], 3),
                ],
                "background_color": self.background_color,
            },
            "valve_types": {
                type_id: spec.to_dict()
                for type_id, spec in self.valve_types.items()
            },
            "elements": [element.to_dict() for element in self.elements],
            "pipes": [pipe.to_dict() for pipe in self.pipes],
        }

    def element_by_id(self, element_id: str) -> ActuatedElementConfig:
        for element in self.elements:
            if element.id == element_id:
                return element
        raise KeyError(f"Unknown element id: {element_id}")

    def pipe_by_id(self, pipe_id: str) -> PipeConfig:
        for pipe in self.pipes:
            if pipe.id == pipe_id:
                return pipe
        raise KeyError(f"Unknown pipe id: {pipe_id}")

    def type_spec_for(self, element_type: str) -> ValveTypeSpec:
        if element_type in self.valve_types:
            return self.valve_types[element_type]
        # Be permissive so older configs still draw even if type definitions are missing.
        return ValveTypeSpec(
            type_id=element_type,
            display_name=element_type.replace("_", " ").title(),
            shape="circle",
        )

    def used_relays(self, *, exclude_element_id: str | None = None) -> set[int]:
        relays: set[int] = set()
        for element in self.elements:
            if exclude_element_id is not None and element.id == exclude_element_id:
                continue
            if element.relay_number is not None:
                relays.add(element.relay_number)
        return relays


    def relay_usage(self) -> dict[int, list[ActuatedElementConfig]]:
        """Return a mapping from relay number to all elements using it."""
        usage: dict[int, list[ActuatedElementConfig]] = {}
        for element in self.elements:
            if element.relay_number is None:
                continue
            usage.setdefault(int(element.relay_number), []).append(element)
        return usage

    def validate_relays(self, *, relay_count: int = 24) -> list[str]:
        """Return human-readable validation messages for relay bindings."""
        messages: list[str] = []
        usage = self.relay_usage()
        for element in self.elements:
            if element.relay_number is None:
                messages.append(f"{element.id}: no relay binding")
            elif not (1 <= int(element.relay_number) <= relay_count):
                messages.append(f"{element.id}: relay {element.relay_number} outside valid range 1-{relay_count}")
        for relay, elements in sorted(usage.items()):
            if len(elements) > 1:
                names = ", ".join(element.id for element in elements)
                messages.append(f"Relay {relay} is assigned to multiple elements: {names}")
        return messages

    def unused_relays(self, *, relay_count: int = 24) -> list[int]:
        used = set(self.relay_usage().keys())
        return [relay for relay in range(1, relay_count + 1) if relay not in used]

    def next_element_id(self, prefix: str = "element") -> str:
        existing = {element.id for element in self.elements}
        index = 1
        while True:
            candidate = f"{prefix}_{index:02d}"
            if candidate not in existing:
                return candidate
            index += 1

    def next_pipe_id(self) -> str:
        existing = {pipe.id for pipe in self.pipes}
        index = 1
        while True:
            candidate = f"pipe_{index:03d}"
            if candidate not in existing:
                return candidate
            index += 1


def default_valve_types_as_dict() -> dict[str, dict[str, str]]:
    return {
        "solenoid_2_way": {
            "display_name": "2-Way Solenoid Valve",
            "shape": "circle",
            "description": "Simple on/off solenoid valve or relay-driven valve.",
        },
        "solenoid_3_way": {
            "display_name": "3-Way Solenoid Valve",
            "shape": "diamond",
            "description": "Directional pneumatic valve.",
        },
        "selector_valve": {
            "display_name": "Selector / Routing Valve",
            "shape": "hexagon",
            "description": "Routing valve, manifold selector, or switching element.",
        },
        "pneumatic_actuator": {
            "display_name": "Pneumatic Actuator",
            "shape": "rounded_rect",
            "description": "Cylinder, bladder, gripper, or other actuated output.",
        },
        "pump_or_source": {
            "display_name": "Pump / Pressure Source",
            "shape": "triangle",
            "description": "Pressure source, vacuum source, or pump enable relay.",
        },
    }
