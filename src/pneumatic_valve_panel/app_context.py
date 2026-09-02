from __future__ import annotations

import logging
from dataclasses import dataclass

from .actuators import ActuatorRegistry
from .controllers.pneumatic_controller import PneumaticController
from .data import DataHub, SensorDefinition, StreamHub
from .hardware import DeviceManager
from .models import PanelConfig


@dataclass
class AppContext:
    """Shared services provided to dashboard tile factories.

    GUI tiles normally use ``data_hub`` because it emits Qt-safe, rate-limited
    signals.  Background consumers and future automation code should use
    ``stream_hub`` directly.  Commands should go through ``device_manager`` or
    the higher-level pneumatic controller.
    """

    panel_config: PanelConfig
    actuator_registry: ActuatorRegistry
    controller: PneumaticController
    data_hub: DataHub
    stream_hub: StreamHub
    device_manager: DeviceManager
    sensor_definitions: dict[str, SensorDefinition]
    logger: logging.Logger
