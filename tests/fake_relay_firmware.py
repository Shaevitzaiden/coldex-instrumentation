"""A Python stand-in for firmware/relay_controls/relay_controls.ino.

It behaves like a ``serial.Serial`` object connected to the Due, so the host
driver can be tested without hardware. Keep it in step with the sketch: it is
also the most precise written description of protocol v2.
"""

from __future__ import annotations

import time


class FakeRelayFirmware:
    SWITCH_DELAY_S = 0.100

    def __init__(self, *, boot_requests_ignored: int = 0, identity: str | None = None) -> None:
        self.is_open = True
        self.timeout = 0.05
        self.states = [False] * 24
        self.manual: set[int] = set()        # zero-based channels in MANUAL
        self.faults: set[int] = set()        # zero-based channels with readback faults
        self.last_switch = [-1.0] * 24
        self.boot_requests_ignored = boot_requests_ignored
        self.identity = identity or "I,coldex_relay_controller,2,24"
        self.silent = False                  # simulate a dead/unplugged controller
        self.received: list[str] = []
        self._rx = b""
        self._tx = b""

    # -- serial.Serial surface used by SerialCommunicator ---------------
    def write(self, data: bytes) -> int:
        self._rx += data
        while b">" in self._rx:
            frame, self._rx = self._rx.split(b">", 1)
            if b"<" not in frame:
                continue
            body = frame.rsplit(b"<", 1)[1].decode()
            self.received.append(body)
            if self.boot_requests_ignored > 0:
                self.boot_requests_ignored -= 1  # still booting: bytes are lost
                continue
            if self.silent:
                continue
            self._tx += (self._handle(body) + "\n").encode()
        return len(data)

    def flush(self) -> None:
        pass

    def read_until(self, terminator: bytes = b"\n") -> bytes:
        if terminator in self._tx:
            line, self._tx = self._tx.split(terminator, 1)
            return line + terminator
        return b""

    def reset_input_buffer(self) -> None:
        self._tx = b""

    def close(self) -> None:
        self.is_open = False

    # -- firmware behaviour ---------------------------------------------
    def _handle(self, body: str) -> str:
        if body == "?":
            states = "".join(
                "E" if i in self.faults else ("1" if s else "0") for i, s in enumerate(self.states)
            )
            modes = "".join("M" if i in self.manual else "A" for i in range(24))
            return f"S,{states},{modes}"
        if body == "I":
            return self.identity
        if body == "X":
            self.states = [False] * 24
            return "1"
        if len(body) == 1 and not body.isdigit():
            return "0,7"
        parts = body.split(",")
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            return "0,1"
        channel, state = int(parts[0]), int(parts[1])
        if channel >= 24:
            return "0,2"
        if state not in (0, 1):
            return "0,3"
        if channel in self.manual:
            return "0,6"
        if self.states[channel] == bool(state):
            return "0,5" if channel in self.faults else "1"
        now = time.monotonic()
        if now - self.last_switch[channel] < self.SWITCH_DELAY_S:
            return "0,4"
        self.states[channel] = bool(state)
        self.last_switch[channel] = now
        return "0,5" if channel in self.faults else "1"
