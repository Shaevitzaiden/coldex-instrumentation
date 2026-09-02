from __future__ import annotations

import logging
from typing import Any

from ..actuators import ActuatorRegistry
from ..models import ActuatedElementConfig, PanelConfig


class PneumaticController:
    """Translate pneumatic-panel element actions into logical actuator commands.

    The panel document stores only ``actuator_id``.  Physical device/relay
    routing is resolved by the shared :class:`ActuatorRegistry` when the command
    is submitted, so editing a relay binding updates every command producer at
    once.
    """

    def __init__(
        self,
        *,
        panel_config: PanelConfig,
        actuator_registry: ActuatorRegistry,
        communicator: Any = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.panel_config = panel_config
        self.actuator_registry = actuator_registry
        self.communicator = communicator
        self.logger = logger or logging.getLogger(__name__)

    def set_communicator(self, communicator: Any | None) -> None:
        self.communicator = communicator

    def set_panel_config(self, panel_config: PanelConfig) -> None:
        self.panel_config = panel_config

    def set_element_state(self, element_id: str, is_active: bool) -> None:
        element = self.panel_config.element_by_id(element_id)
        self._send_to_communicator(element, is_active)

    def close_all(self) -> None:
        for element in self.panel_config.elements:
            if element.enabled:
                self._send_to_communicator(element, is_active=False)
                element.initially_active = False

    def _send_to_communicator(self, element: ActuatedElementConfig, is_active: bool) -> None:
        if self.communicator is None:
            self.logger.warning(
                "No communicator attached. Ignoring element request: %s -> %s",
                element.id,
                "ACTIVE" if is_active else "INACTIVE",
            )
            return
        if not element.actuator_id:
            raise ValueError(f"Panel element {element.id!r} has no actuator binding")

        metadata = dict(element.metadata)
        metadata.pop("_legacy_relay_number", None)
        metadata.setdefault("element_type", element.element_type)
        metadata.setdefault("label", element.label)
        metadata.setdefault("origin", "user.pneumatic_panel")

        # Preferred registry-aware API.
        if hasattr(self.communicator, "set_actuator_state"):
            self.communicator.set_actuator_state(
                actuator_id=element.actuator_id,
                is_active=is_active,
                element_id=element.id,
                element_type=element.element_type,
                metadata=metadata,
            )
            return

        # Compatibility for an older communicator that does not understand
        # logical actuator IDs.  Resolve the central binding here rather than
        # falling back to a relay stored in the panel document.
        actuator = self.actuator_registry.get(element.actuator_id)
        metadata.setdefault("device_id", actuator.device_id)
        if hasattr(self.communicator, "set_element_state"):
            self.communicator.set_element_state(
                element_id=element.id,
                element_type=element.element_type,
                is_active=is_active,
                relay_number=actuator.relay_number,
                metadata=metadata,
            )
            return
        if hasattr(self.communicator, "set_valve_state"):
            self.communicator.set_valve_state(
                valve_id=element.id,
                is_open=is_active,
                command_id=actuator.relay_number,
                metadata=metadata,
            )
            return
        raise TypeError(
            "Communicator must define set_actuator_state(...), "
            "set_element_state(...), or set_valve_state(...)"
        )
