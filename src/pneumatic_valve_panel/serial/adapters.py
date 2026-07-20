from __future__ import annotations

from typing import Any


class RelayMethodAdapter:
    """Example adapter for a communicator with separate relay on/off methods.

    Example expected wrapped API::

        hardware.set_relay(relay_number=3, enabled=True)

    You can delete or replace this file when integrating your own serial layer.
    """

    def __init__(self, hardware: Any) -> None:
        self.hardware = hardware

    def set_element_state(
        self,
        *,
        element_id: str,
        element_type: str,
        is_active: bool,
        relay_number: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if relay_number is None:
            raise ValueError(f"Element {element_id!r} does not have a relay binding")
        self.hardware.set_relay(relay_number=relay_number, enabled=is_active)
