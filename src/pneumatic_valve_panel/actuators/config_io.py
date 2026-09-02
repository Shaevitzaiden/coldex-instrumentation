from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml

from .models import ActuatorDefinition


def load_actuator_definitions(path: str | Path) -> dict[str, ActuatorDefinition]:
    path = Path(path)
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw_actuators = raw.get("actuators", raw)
    return {
        str(actuator_id): ActuatorDefinition.from_dict(str(actuator_id), data or {})
        for actuator_id, data in raw_actuators.items()
    }


def save_actuator_definitions(
    definitions: Iterable[ActuatorDefinition],
    path: str | Path,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "actuators": {
            definition.actuator_id: definition.to_dict()
            for definition in definitions
        },
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
