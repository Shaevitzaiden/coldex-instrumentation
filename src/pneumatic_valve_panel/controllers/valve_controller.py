from __future__ import annotations

import logging
from typing import Optional

from ..models import PanelConfig, ValveButtonConfig
from ..serial.protocols import ValveCommunicator


class ValveController:
    """Application-layer boundary between the GUI and serial communication.

    The GUI calls this controller. The controller validates the valve id, builds
    the command payload, and delegates the actual hardware/firmware interaction
    to the injected communicator object.
    """

    def __init__(
        self,
        *,
        panel_config: PanelConfig,
        communicator: Optional[ValveCommunicator] = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.panel_config = panel_config
        self.communicator = communicator
        self.logger = logger or logging.getLogger(__name__)

    def set_communicator(self, communicator: ValveCommunicator | None) -> None:
        self.communicator = communicator

    def set_panel_config(self, panel_config: PanelConfig) -> None:
        self.panel_config = panel_config

    def set_valve_state(self, valve_id: str, is_open: bool) -> None:
        button_config = self.panel_config.button_by_id(valve_id)
        self._send_to_communicator(button_config, is_open)

    def close_all(self) -> None:
        for button_config in self.panel_config.buttons:
            if button_config.enabled:
                self._send_to_communicator(button_config, is_open=False)

    def _send_to_communicator(self, button_config: ValveButtonConfig, is_open: bool) -> None:
        if self.communicator is None:
            self.logger.warning(
                "No communicator attached. Ignoring valve request: %s -> %s",
                button_config.id,
                "OPEN" if is_open else "CLOSED",
            )
            return

        self.communicator.set_valve_state(
            valve_id=button_config.id,
            is_open=is_open,
            command_id=button_config.command_id,
            metadata=button_config.metadata,
        )
