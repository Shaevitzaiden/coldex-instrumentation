from __future__ import annotations

import logging
from dataclasses import dataclass

from .controllers.pneumatic_controller import PneumaticController
from .data import DataHub, SensorDefinition
from .models import PanelConfig


@dataclass
class AppContext:
    """Shared application services provided to dashboard tile factories."""

    panel_config: PanelConfig
    controller: PneumaticController
    data_hub: DataHub
    sensor_definitions: dict[str, SensorDefinition]
    logger: logging.Logger
