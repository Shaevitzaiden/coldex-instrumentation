from __future__ import annotations

"""Helpers for grouping sensor channels by physical measurement type.

The GUI has several tile types that need to answer a question such as:

    "Can these channels sensibly share one y-axis?"

A sensor's explicit ``metadata.quantity`` is the preferred answer.  For older
configuration files that do not yet provide that metadata, this module falls
back to a small unit-to-quantity map.  Finally, unknown non-empty units are
used as their own compatibility group.

The grouping key intentionally contains both *quantity* and *unit*.  Two
sensors may both measure temperature, but plotting °C and °F on one unconverted
y-axis would be misleading.  Treating ``temperature + °C`` and
``temperature + °F`` as separate groups prevents that accidental mismatch.
"""

from dataclasses import dataclass
from typing import Iterable

from .models import SensorDefinition


# Common unit spellings used only as a backwards-compatible semantic fallback.
# New projects should prefer ``metadata: {quantity: ...}`` in sensors.yaml.
_UNIT_TO_QUANTITY = {
    "°c": "temperature",
    "degc": "temperature",
    "celsius": "temperature",
    "°f": "temperature",
    "degf": "temperature",
    "fahrenheit": "temperature",
    "k": "temperature",
    "kelvin": "temperature",
    "pa": "pressure",
    "kpa": "pressure",
    "mpa": "pressure",
    "bar": "pressure",
    "mbar": "pressure",
    "psi": "pressure",
    "torr": "pressure",
    "mtorr": "pressure",
    "atm": "pressure",
    "%rh": "humidity",
    "rh": "humidity",
    "l/min": "flow_rate",
    "lpm": "flow_rate",
    "ml/min": "flow_rate",
    "slm": "flow_rate",
    "sccm": "flow_rate",
}


@dataclass(frozen=True, order=True)
class SensorGroupKey:
    """A compatibility group for one-axis sensor visualization."""

    quantity: str
    unit: str


def _normalized_unit(unit: str) -> str:
    return str(unit or "").strip().replace(" ", "").lower()


def sensor_quantity(definition: SensorDefinition) -> str:
    """Return a stable physical-quantity key for one sensor definition.

    Preference order:

    1. explicit ``metadata.quantity``;
    2. a known unit -> quantity mapping;
    3. the unit itself as a generic semantic group;
    4. the sensor ID, so unrelated unitless sensors are *not* accidentally
       treated as compatible.
    """

    explicit = str((definition.metadata or {}).get("quantity", "")).strip().lower()
    if explicit:
        return explicit

    unit_key = _normalized_unit(definition.unit)
    if unit_key in _UNIT_TO_QUANTITY:
        return _UNIT_TO_QUANTITY[unit_key]
    if unit_key:
        return f"unit:{unit_key}"

    return f"sensor:{definition.sensor_id}"


def sensor_group_key(definition: SensorDefinition) -> SensorGroupKey:
    """Return the same-axis compatibility key for a sensor."""

    return SensorGroupKey(
        quantity=sensor_quantity(definition),
        unit=str(definition.unit or "").strip(),
    )


def humanize_quantity(quantity: str) -> str:
    """Convert an internal quantity key into concise UI text."""

    if quantity.startswith("unit:"):
        return quantity.split(":", 1)[1]
    if quantity.startswith("sensor:"):
        return "Sensor"
    return quantity.replace("_", " ").strip().title() or "Sensor"


def sensor_group_label(key: SensorGroupKey) -> str:
    """Human-readable label such as ``Temperature [°C]``."""

    base = humanize_quantity(key.quantity)
    return f"{base} [{key.unit}]" if key.unit else base


def available_sensor_groups(
    definitions: Iterable[SensorDefinition],
) -> list[SensorGroupKey]:
    """Return sorted unique groups for enabled sensors."""

    groups = {
        sensor_group_key(definition)
        for definition in definitions
        if definition.enabled
    }
    return sorted(groups, key=lambda key: sensor_group_label(key).lower())


def validate_same_sensor_group(
    sensor_ids: Iterable[str],
    definitions: dict[str, SensorDefinition],
) -> SensorGroupKey | None:
    """Validate that all requested sensors can share one plot axis.

    Returns the shared group.  Raises ``ValueError`` for an unknown/disabled
    sensor or when the selected channels belong to different quantity/unit
    groups.  ``None`` is returned for an empty selection.
    """

    group: SensorGroupKey | None = None
    for sensor_id in sensor_ids:
        definition = definitions.get(sensor_id)
        if definition is None:
            raise ValueError(f"Unknown sensor channel: {sensor_id}")
        if not definition.enabled:
            raise ValueError(f"Sensor channel is disabled: {sensor_id}")

        current = sensor_group_key(definition)
        if group is None:
            group = current
        elif current != group:
            raise ValueError(
                "Plot + readout tiles require one compatible measurement group. "
                f"{sensor_id!r} belongs to {sensor_group_label(current)!r}, "
                f"but the first selected channel belongs to {sensor_group_label(group)!r}."
            )
    return group
