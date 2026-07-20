"""Modular PyQt5 pneumatic valve control panel.

Import GUI objects from their concrete modules, for example:

    from pneumatic_valve_panel.app import run_app

Keeping this package initializer lightweight makes non-GUI modules such as the
YAML config loader importable even before PyQt5 is installed.
"""

from .models import AttachedLine, PanelConfig, PanelLine, ValveButtonConfig

__all__ = [
    "AttachedLine",
    "PanelConfig",
    "PanelLine",
    "ValveButtonConfig",
]
