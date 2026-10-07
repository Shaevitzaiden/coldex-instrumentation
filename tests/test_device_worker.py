"""DeviceWorker connection handling, run in a plain thread (no Qt event loop)."""

from __future__ import annotations

import queue
import threading
import time

from pneumatic_valve_panel.data.models import CommandResult, DeviceCommand, DeviceDefinition
from pneumatic_valve_panel.data.stream_hub import StreamHub
from pneumatic_valve_panel.hardware.device_manager import DeviceWorker


class FlakyDevice:
    """Fails to connect ``failures`` times, then works until ``unplug()``."""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.connect_calls = 0
        self.unplugged = False
        self.commands: list[bool] = []

    def connect(self, port: str = "") -> None:
        self.connect_calls += 1
        if self.connect_calls <= self.failures:
            raise OSError(f"could not open port {port}")
        self.unplugged = False

    def disconnect(self) -> None:
        pass

    def unplug(self) -> None:
        self.unplugged = True

    def set_element_state(self, *, element_id, element_type, is_active, relay_number=None, metadata=None):
        self.commands.append(is_active)

    def read_available_packets(self, timeout_s: float = 0.01):
        if self.unplugged:
            raise OSError("ClearCommError failed (device removed)")
        return []


def start_worker(device, hub):
    definition = DeviceDefinition(
        device_id="dev", connection={"port": "COM_TEST"}, reconnect_interval_s=0.1
    )
    commands: queue.Queue = queue.Queue()
    worker = DeviceWorker(
        definition=definition, communicator=device, command_queue=commands,
        stream_hub=hub, channel_map={},
    )
    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()
    return worker, thread, commands


def wait_for(condition, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return False


def command(active: bool) -> DeviceCommand:
    return DeviceCommand(
        device_id="dev",
        command_type="set_element_state",
        payload={"element_id": "valve_01", "is_active": active, "relay_number": 1},
    )


def test_worker_retries_until_device_connects_then_recovers_from_unplug():
    hub = StreamHub()
    statuses = hub.subscribe("devices/status/*")
    device = FlakyDevice(failures=2)
    worker, thread, _ = start_worker(device, hub)
    try:
        assert wait_for(lambda: device.connect_calls == 3)
        assert wait_for(lambda: hub.latest("devices/status/dev").connected)
        messages = [envelope.payload.message for envelope in statuses.drain()]
        assert any("could not open port COM_TEST" in m for m in messages)

        device.unplug()
        assert wait_for(lambda: device.connect_calls == 4)  # reconnected
        assert wait_for(lambda: hub.latest("devices/status/dev").connected)
    finally:
        worker.stop()
        thread.join(2)
    assert not thread.is_alive()


def test_commands_while_offline_fail_immediately():
    hub = StreamHub()
    results = hub.subscribe("commands/results/*")
    device = FlakyDevice(failures=10_000)
    worker, thread, commands = start_worker(device, hub)
    try:
        commands.put(command(True))
        assert wait_for(lambda: results.qsize() > 0)
        result: CommandResult = results.get_nowait().payload
        assert result.success is False
        assert "not connected" in result.message
        assert device.commands == []
    finally:
        worker.stop()
        thread.join(2)


def test_relay_state_packets_are_published():
    hub = StreamHub()
    results = hub.subscribe("commands/results/*")

    class Reporter(FlakyDevice):
        sent = False

        def read_available_packets(self, timeout_s=0.01):
            if self.sent:
                return []
            self.sent = True
            return [{"type": "relay_states", "states": {1: True, 2: False}, "faults": [2], "manual": []}]

    worker, thread, _ = start_worker(Reporter(failures=0), hub)
    try:
        assert wait_for(lambda: results.qsize() > 0)
        result = results.get_nowait().payload
        assert result.command_type == "relay_states"
        assert result.payload["states"] == {1: True, 2: False}
        assert result.payload["faults"] == [2]
    finally:
        worker.stop()
        thread.join(2)
