"""Reference drivers for the vacuum-instrumentation bundle.

Analog conversion helpers are dependency-free. Serial-backed classes are loaded
lazily so conversion/unit tests can run even in documentation/build environments
where ``pyserial`` is not installed yet. Normal installations should install the
repository requirements, which include pyserial.
"""

from .analog import AnalogPressure, gp475_voltage_to_pressure, pdr_d1_voltage_to_pressure

__all__ = [
    "AnalogPressure",
    "gp475_voltage_to_pressure",
    "pdr_d1_voltage_to_pressure",
    "GraphixController",
    "GraphixPressure",
    "GraphixError",
    "GraphixNack",
    "AdaloggerDAQ",
]


def __getattr__(name: str):
    if name in {"GraphixController", "GraphixPressure", "GraphixError", "GraphixNack"}:
        from . import graphix
        return getattr(graphix, name)
    if name == "AdaloggerDAQ":
        from .usb_daq import AdaloggerDAQ
        return AdaloggerDAQ
    raise AttributeError(name)
