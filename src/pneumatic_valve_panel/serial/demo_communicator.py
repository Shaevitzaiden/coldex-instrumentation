from __future__ import annotations

from typing import Any, Mapping


class DemoCommunicator:
    """No-hardware communicator used for development and GUI layout work."""

    def __init__(self) -> None:
        self.last_states: dict[str, bool] = {}

    def set_valve_state(
        self,
        *,
        valve_id: str,
        is_open: bool,
        command_id: Any = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self.last_states[valve_id] = is_open
        state = "OPEN" if is_open else "CLOSED"
        print(
            f"[DemoCommunicator] valve_id={valve_id!r}, "
            f"command_id={command_id!r}, state={state}, metadata={dict(metadata or {})}"
        )
