from __future__ import annotations

"""Persistent definitions for globally addressable actuators.

An actuator is the application's logical name for one commandable hardware
output.  Dashboard widgets and the pneumatic schematic reference ``actuator_id``;
only this model knows which physical device/relay implements that actuator.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass
class ActuatorDefinition:
    """One globally named commandable output.

    ``device_id`` + ``relay_number`` is the physical binding.  The remaining
    fields describe semantics/UI and can evolve without changing hardware
    routing code.
    """

    actuator_id: str
    label: str
    kind: str = "relay"
    device_id: str = "controller"
    relay_number: int | None = None
    enabled: bool = True
    default_active: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, actuator_id: str, data: Mapping[str, Any]) -> "ActuatorDefinition":
        raw_relay = data.get("relay_number", data.get("relay"))
        relay_number = None if raw_relay in (None, "", 0, "0") else int(raw_relay)
        return cls(
            actuator_id=str(actuator_id),
            label=str(data.get("label", actuator_id)),
            kind=str(data.get("kind", "relay")),
            device_id=str(data.get("device_id", "controller")),
            relay_number=relay_number,
            enabled=bool(data.get("enabled", True)),
            default_active=bool(data.get("default_active", False)),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "label": self.label,
            "kind": self.kind,
            "device_id": self.device_id,
            "relay_number": self.relay_number,
            "enabled": self.enabled,
            "default_active": self.default_active,
        }
        if self.metadata:
            data["metadata"] = dict(self.metadata)
        return data
