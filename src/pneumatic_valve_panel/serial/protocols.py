from __future__ import annotations

from typing import Any, Protocol


class ValveCommunicator(Protocol):
    """Compatibility protocol from the previous barebones version.

    Existing user code can keep implementing this method. The new controller also
    supports ``set_element_state(...)`` if your newer abstraction has a more
    generic element-oriented API.
    """

    def set_valve_state(
        self,
        *,
        valve_id: str,
        is_open: bool,
        command_id: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        ...


class PneumaticCommunicator(Protocol):
    """Preferred generic protocol for the editor version."""

    def set_element_state(
        self,
        *,
        element_id: str,
        element_type: str,
        is_active: bool,
        relay_number: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        ...
