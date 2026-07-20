from __future__ import annotations

from typing import Any, Callable, Mapping


class CallableCommunicatorAdapter:
    """Wrap a plain function so it can be used as a ValveCommunicator.

    The wrapped callable receives keyword arguments:
    ``valve_id``, ``is_open``, ``command_id``, and ``metadata``.
    """

    def __init__(self, callback: Callable[..., None]) -> None:
        self.callback = callback

    def set_valve_state(
        self,
        *,
        valve_id: str,
        is_open: bool,
        command_id: Any = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self.callback(
            valve_id=valve_id,
            is_open=is_open,
            command_id=command_id,
            metadata=metadata or {},
        )


class HighLowPinAdapter:
    """Adapter for legacy-style objects with set_pin_high / set_pin_low methods.

    This is included only as an example. In new code, prefer implementing
    ``set_valve_state(...)`` directly on your serial communicator.
    """

    def __init__(self, target: Any) -> None:
        self.target = target

    def set_valve_state(
        self,
        *,
        valve_id: str,
        is_open: bool,
        command_id: Any = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if command_id is None:
            raise ValueError(f"Valve {valve_id!r} does not define a command_id/pin.")
        if is_open:
            self.target.set_pin_high(command_id)
        else:
            self.target.set_pin_low(command_id)
