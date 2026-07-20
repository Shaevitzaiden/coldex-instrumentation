from __future__ import annotations

from typing import Any, Mapping, Protocol


class ValveCommunicator(Protocol):
    """Minimal interface expected by the valve GUI.

    Your custom serial communicator can implement this method directly. The GUI
    does not need to know whether ``command_id`` is an Arduino pin, a valve name,
    a firmware channel, a structured command, or something else.
    """

    def set_valve_state(
        self,
        *,
        valve_id: str,
        is_open: bool,
        command_id: Any = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        ...
