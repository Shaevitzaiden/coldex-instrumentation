from __future__ import annotations

import logging
from typing import Any

from ..models import ActuatedElementConfig, PanelConfig


class PneumaticController:
    """Boundary between GUI elements and the user-provided serial communicator."""

    def __init__(
        self,
        *,
        panel_config: PanelConfig,
        communicator: Any = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.panel_config = panel_config
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

        metadata = dict(element.metadata)
        metadata.setdefault("element_type", element.element_type)
        metadata.setdefault("label", element.label)

        # Preferred new API: generic actuated element state.
        if hasattr(self.communicator, "set_element_state"):
            self.communicator.set_element_state(
                element_id=element.id,
                element_type=element.element_type,
                is_active=is_active,
                relay_number=element.relay_number,
                metadata=metadata,
            )
            return

        # Backwards-compatible API from the first barebones version.
        if hasattr(self.communicator, "set_valve_state"):
            self.communicator.set_valve_state(
                valve_id=element.id,
                is_open=is_active,
                command_id=element.relay_number,
                metadata=metadata,
            )
            return

        raise TypeError(
            "Communicator must define set_element_state(...) or set_valve_state(...)"
        )
