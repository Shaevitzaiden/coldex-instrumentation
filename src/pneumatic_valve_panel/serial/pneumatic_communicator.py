from __future__ import annotations

"""Serial driver for the Arduino Due relay controller (firmware protocol v2).

Wire protocol (see firmware/relay_controls/relay_controls.ino)
--------------------------------------------------------------
Every command is framed as ``<...>`` and answered with one line:

======== ============================ =======================================
Command  Reply                        Meaning
======== ============================ =======================================
<n,s>    ``1`` or ``0,<code>``        set zero-based relay ``n`` to ``s``
<?>      ``S,<states>,<modes>``       one character per relay (see below)
<I>      ``I,<firmware>,<ver>,<n>``   identity handshake
<X>      ``1``                        release every relay immediately
======== ============================ =======================================

Lines beginning with ``#`` are human-readable notes and are ignored.

The firmware cannot see real valve positions. "Active" therefore means the
controller is driving that relay; it does not prove the valve moved.
"""

import re
import time
from typing import Any

from .serial_interface import SerialCommunicator

FIRMWARE_ID = "coldex_relay_controller"
MIN_PROTOCOL_VERSION = 2

ERROR_MESSAGES = {
    1: "controller could not parse the command",
    2: "relay number is outside the controller's range",
    3: "requested state must be 0 or 1",
    4: "relay was switched less than 100 ms ago; try again",
    5: "relay output pin did not read back the commanded level (wiring fault?)",
    6: "switch panel has this channel in MANUAL; automated control is blocked",
    7: "controller did not recognise the command",
}

_FAILURE_RE = re.compile(r"^0(?:,(\d+))?$")


class RelayControllerError(RuntimeError):
    """The controller answered, but refused or failed the command."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class PneumaticCommunicator(SerialCommunicator):
    """Command-capable driver for the pneumatic relay controller.

    The DeviceWorker calls these methods from the controller's own thread:

    * ``connect``/``disconnect`` once per connection attempt;
    * ``set_element_state`` for each relay command from the GUI;
    * ``read_available_packets`` continuously. It polls the controller's
      status about once per second and returns a ``relay_states`` packet
      whenever the reported states change, so the valve panel can follow the
      controller after a reset.
    """

    def __init__(self, *, status_poll_interval_s: float = 1.0, max_missed_polls: int = 3) -> None:
        super().__init__()
        self.configure_msg_structure("outbound", start_character="<", end_character=">")
        self.status_poll_interval_s = float(status_poll_interval_s)
        self.max_missed_polls = int(max_missed_polls)
        self.relay_count = 24
        self.firmware_identity: str | None = None
        self._last_reported: tuple[str, str] | None = None
        self._next_poll_monotonic = 0.0
        self._missed_polls = 0
        self._legacy_firmware = False

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    def connect(
        self,
        port: str | None = None,
        *,
        baudrate: int | None = None,
        timeout_s: float = 0.05,
        boot_wait_s: float = 3.0,
        verify_identity: bool = True,
    ) -> None:
        """Open the port and confirm the controller firmware answers.

        Opening the Due's programming port usually resets the board, so the
        identity request is retried for up to ``boot_wait_s`` seconds while it
        boots. Set ``verify_identity: false`` in devices.yaml only to talk to
        pre-v2 firmware (no status polling or error codes in that case).
        """
        if not port:
            raise ValueError("devices.yaml: the relay controller needs connection.port (e.g. COM14)")
        if baudrate is None:
            raise ValueError("devices.yaml: the relay controller needs connection.baudrate (9600)")
        super().connect(port=port, baud_rate=baudrate, timeout=timeout_s, sleep_time=0.0)

        self._last_reported = None
        self._next_poll_monotonic = 0.0
        self._missed_polls = 0
        self.firmware_identity = None
        self._legacy_firmware = not verify_identity
        if verify_identity:
            self._wait_for_identity(port, boot_wait_s)

    def _wait_for_identity(self, port: str, boot_wait_s: float) -> None:
        deadline = time.monotonic() + boot_wait_s
        last_reply = ""
        while time.monotonic() < deadline:
            try:
                reply = self._transact("I", timeout_s=0.3)
            except TimeoutError:
                continue
            last_reply = reply
            fields = reply.split(",")
            if len(fields) >= 4 and fields[0] == "I" and fields[1] == FIRMWARE_ID:
                version = int(fields[2]) if fields[2].isdigit() else 0
                if version < MIN_PROTOCOL_VERSION:
                    raise ConnectionError(
                        f"Relay controller on {port} runs protocol v{version}; "
                        f"v{MIN_PROTOCOL_VERSION}+ is required. Re-flash relay_controls.ino."
                    )
                self.relay_count = int(fields[3]) if fields[3].isdigit() else self.relay_count
                self.firmware_identity = reply
                return
        self.disconnect()
        hint = f" (last reply: {last_reply!r})" if last_reply else ""
        raise ConnectionError(
            f"No relay controller answered on {port}{hint}. Check the COM port in "
            "devices.yaml and that relay_controls.ino (protocol v2) is flashed."
        )

    def disconnect(self) -> None:
        super().disconnect()

    # ------------------------------------------------------------------
    # Low-level request/reply
    # ------------------------------------------------------------------
    def _transact(self, body: str, timeout_s: float = 0.5) -> str:
        """Send one framed command and return its first non-note reply line."""
        # Drop anything left over (a late reply, boot notes) so it cannot be
        # mistaken for the answer to this command.
        self._require_connection().reset_input_buffer()
        self.write(body)
        deadline = time.monotonic() + timeout_s
        notes: list[str] = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                line = self.read(timeout=remaining).strip()
            except TimeoutError:
                break
            if not line or line.startswith("#"):
                continue
            if self._legacy_firmware and line not in {"0", "1"}:
                # Pre-v2 firmware printed debug lines before its 1/0 reply.
                notes.append(line)
                continue
            return line
        suffix = f"; received {notes!r}" if notes else ""
        raise TimeoutError(f"Relay controller did not answer {body!r}{suffix}")

    @staticmethod
    def _raise_for_reply(reply: str, command: str) -> None:
        if reply == "1":
            return
        match = _FAILURE_RE.match(reply)
        if match is None:
            raise RelayControllerError(f"Unexpected reply {reply!r} to {command!r}")
        code = int(match.group(1)) if match.group(1) else None
        reason = ERROR_MESSAGES.get(code, "command rejected") if code else "command rejected"
        raise RelayControllerError(reason, code=code)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    def set_element_state(
        self,
        *,
        element_id: str,
        element_type: str,
        is_active: bool,
        relay_number: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Set one one-based relay binding (as used in actuators.yaml)."""
        del element_type, metadata  # Part of the common command interface.
        if relay_number is None:
            raise ValueError(f"{element_id} has no relay binding")
        if not 1 <= int(relay_number) <= self.relay_count:
            raise ValueError(
                f"{element_id}: relay {relay_number} is outside 1..{self.relay_count}"
            )

        # Firmware addresses relays from 0; YAML/UI bindings are 1..N.
        command = f"{int(relay_number) - 1},{int(bool(is_active))}"
        self._raise_for_reply(self._transact(command), command)
        # Report the new state promptly rather than waiting for the next poll.
        self._next_poll_monotonic = 0.0

    def release_all(self) -> None:
        """Release every relay at once (firmware ``<X>``)."""
        self._raise_for_reply(self._transact("X"), "X")
        self._next_poll_monotonic = 0.0

    def execute_command(self, command: Any) -> None:
        """Generic DeviceWorker hook for non-relay commands."""
        if getattr(command, "command_type", None) == "release_all":
            self.release_all()
            return
        raise TypeError(f"Relay controller does not support {command.command_type!r}")

    def query_status(self) -> dict[str, Any]:
        """Return the controller's per-relay status (one-based relay numbers)."""
        reply = self._transact("?", timeout_s=0.5)
        fields = reply.split(",")
        if len(fields) != 3 or fields[0] != "S":
            raise RelayControllerError(f"Unexpected status reply {reply!r}")
        states_text, modes_text = fields[1], fields[2]
        return self._status_packet(states_text, modes_text)

    @staticmethod
    def _status_packet(states_text: str, modes_text: str) -> dict[str, Any]:
        states: dict[int, bool] = {}
        faults: list[int] = []
        manual: list[int] = []
        for index, char in enumerate(states_text, start=1):
            if char == "E":
                faults.append(index)
                states[index] = False
            else:
                states[index] = char == "1"
        for index, char in enumerate(modes_text, start=1):
            if char == "M":
                manual.append(index)
        return {
            "type": "relay_states",
            "states": states,
            "manual": manual,
            "faults": faults,
        }

    # ------------------------------------------------------------------
    # Telemetry (polled by DeviceWorker)
    # ------------------------------------------------------------------
    def read_available_packets(self, timeout_s: float = 0.01) -> list[dict[str, Any]]:
        """Poll relay status about once per second; report only changes."""
        del timeout_s
        if self._legacy_firmware:
            return []
        now = time.monotonic()
        if now < self._next_poll_monotonic:
            return []
        self._next_poll_monotonic = now + self.status_poll_interval_s

        try:
            reply = self._transact("?", timeout_s=0.5)
        except TimeoutError as exc:
            self._missed_polls += 1
            if self._missed_polls >= self.max_missed_polls:
                raise ConnectionError(
                    f"Relay controller stopped answering ({self._missed_polls} missed status polls)"
                ) from exc
            return []
        self._missed_polls = 0

        fields = reply.split(",")
        if len(fields) != 3 or fields[0] != "S":
            return [{
                "type": "log",
                "level": "WARNING",
                "message": f"Unexpected status reply from relay controller: {reply!r}",
            }]
        key = (fields[1], fields[2])
        if key == self._last_reported:
            return []
        self._last_reported = key
        return [self._status_packet(fields[1], fields[2])]


if __name__ == "__main__":
    # Manual bench test: python -m pneumatic_valve_panel.serial.pneumatic_communicator COM14
    import sys

    port = sys.argv[1] if len(sys.argv) > 1 else "COM14"
    communicator = PneumaticCommunicator()
    try:
        communicator.connect(port=port, baudrate=9600, timeout_s=0.5)
        print("Connected:", communicator.firmware_identity)
        print("Commands: '<relay 1-24>,<0|1>', 'status', 'off', 'q'")
        while True:
            raw = input("> ").strip().lower()
            if raw in {"q", "quit", "exit"}:
                break
            try:
                if raw == "status":
                    print(communicator.query_status())
                elif raw == "off":
                    communicator.release_all()
                    print("OK: all relays released")
                else:
                    relay, active = (part.strip() for part in raw.split(",", 1))
                    communicator.set_element_state(
                        element_id=f"relay_{relay}",
                        element_type="relay",
                        relay_number=int(relay),
                        is_active=bool(int(active)),
                    )
                    print("OK")
            except (RelayControllerError, ValueError, TimeoutError) as exc:
                print("FAILED:", exc)
    finally:
        communicator.disconnect()
