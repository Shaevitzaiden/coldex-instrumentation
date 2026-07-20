from __future__ import annotations

from typing import Any


class DemoCommunicator:
    """No-hardware communicator used by ``run_app.py``.

    Replace this with your own serial communicator object, or wrap your object in
    a small adapter. The GUI never opens serial ports directly.
    """

    def set_element_state(
        self,
        *,
        element_id: str,
        element_type: str,
        is_active: bool,
        relay_number: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        print(
            "[DEMO]",
            f"element_id={element_id!r}",
            f"element_type={element_type!r}",
            f"state={'ACTIVE/OPEN' if is_active else 'INACTIVE/CLOSED'}",
            f"relay={relay_number}",
            f"metadata={metadata or {}}",
        )

    # Optional backwards-compatible alias.
    def set_valve_state(
        self,
        *,
        valve_id: str,
        is_open: bool,
        command_id: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.set_element_state(
            element_id=valve_id,
            element_type=str((metadata or {}).get("element_type", "unknown")),
            is_active=is_open,
            relay_number=int(command_id) if command_id is not None else None,
            metadata=metadata,
        )
