"""Conversions for analog pressure-controller outputs.

These functions convert *reconstructed instrument voltage* to pressure. The
RP2040 firmware already applies the resistor-divider reconstruction/calibration,
so host code should pass the emitted ``volts[]`` values directly here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalogPressure:
    source: str
    voltage: float
    pressure: float | None
    unit: str
    valid: bool
    status: str


def gp475_voltage_to_pressure(
    voltage: float,
    unit: str = "Torr",
    mode: str = "0-7V",
) -> AnalogPressure:
    """Convert the Series 475 logarithmic analog output to pressure.

    The default 0–7 V, 1 V/decade relationship in Torr is ``10**(V - 4)``.
    The controller's high-voltage fault/unplugged indication is treated as an
    invalid pressure rather than an enormous numeric value.
    """
    if voltage >= 9.5:
        return AnalogPressure(
            source="gp475",
            voltage=voltage,
            pressure=None,
            unit=unit,
            valid=False,
            status="gauge_unplugged_or_fault",
        )

    exponent_by_mode = {
        "0-7V": {"Torr": -4, "mbar": -4, "Pa": -2},
        "1-8V": {"Torr": -5, "mbar": -5, "Pa": -3},
    }
    if mode not in exponent_by_mode:
        raise ValueError("Only logarithmic 0-7V and 1-8V modes are implemented")
    try:
        exponent = exponent_by_mode[mode][unit]
    except KeyError as exc:
        raise ValueError(f"Unsupported GP475 pressure unit: {unit}") from exc

    return AnalogPressure(
        source="gp475",
        voltage=voltage,
        pressure=10.0 ** (voltage + exponent),
        unit=unit,
        valid=True,
        status="ok",
    )


def pdr_d1_voltage_to_pressure(
    voltage: float,
    full_scale: float,
    unit: str = "Torr",
) -> AnalogPressure:
    """Convert PDR-D-1 0–10 V ``DC OUT`` to the attached Baratron range."""
    if full_scale <= 0:
        raise ValueError("full_scale must be positive")

    valid = -0.1 <= voltage <= 10.5
    pressure = (voltage / 10.0) * full_scale if valid else None
    return AnalogPressure(
        source="pdr_d1",
        voltage=voltage,
        pressure=pressure,
        unit=unit,
        valid=valid,
        status="ok" if valid else "voltage_out_of_range",
    )
