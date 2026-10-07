from __future__ import annotations

import time

import pytest

from pneumatic_valve_panel.serial.pneumatic_communicator import (
    PneumaticCommunicator,
    RelayControllerError,
)


def connect(**kwargs) -> PneumaticCommunicator:
    communicator = PneumaticCommunicator(status_poll_interval_s=0.0)
    communicator.connect(port="COM_TEST", baudrate=9600, boot_wait_s=1.0, **kwargs)
    return communicator


def set_relay(communicator, relay: int, active: bool) -> None:
    communicator.set_element_state(
        element_id=f"valve_{relay}", element_type="valve", is_active=active, relay_number=relay
    )


def test_connect_reads_identity(fake_due):
    communicator = connect()
    assert communicator.firmware_identity == "I,coldex_relay_controller,2,24"
    assert communicator.relay_count == 24


def test_connect_waits_for_board_to_boot(fake_due):
    fake_due.boot_requests_ignored = 2  # the Due resets when the port opens
    communicator = connect()
    assert communicator.firmware_identity is not None
    assert fake_due.received[:3] == ["I", "I", "I"]


def test_connect_rejects_wrong_device(fake_due):
    fake_due.identity = "Some other Arduino sketch"
    with pytest.raises(ConnectionError, match="No relay controller answered"):
        connect()
    assert not fake_due.is_open


def test_connect_rejects_old_protocol(fake_due):
    fake_due.identity = "I,coldex_relay_controller,1,24"
    with pytest.raises(ConnectionError, match="protocol v1"):
        connect()


def test_one_based_relay_numbers_become_zero_based(fake_due):
    communicator = connect()
    set_relay(communicator, 1, True)
    set_relay(communicator, 24, True)
    assert fake_due.received[-2:] == ["0,1", "23,1"]
    assert fake_due.states[0] and fake_due.states[23]


def test_out_of_range_relay_never_reaches_controller(fake_due):
    communicator = connect()
    with pytest.raises(ValueError):
        set_relay(communicator, 25, True)
    with pytest.raises(ValueError):
        set_relay(communicator, 0, True)
    assert fake_due.received == ["I"]


def test_lockout_is_reported_with_reason(fake_due):
    communicator = connect()
    set_relay(communicator, 3, True)
    with pytest.raises(RelayControllerError, match="100 ms") as excinfo:
        set_relay(communicator, 3, False)
    assert excinfo.value.code == 4


def test_repeating_current_state_is_not_locked_out(fake_due):
    communicator = connect()
    set_relay(communicator, 3, True)
    set_relay(communicator, 3, True)  # same state again: accepted immediately


def test_manual_switch_blocks_automation(fake_due):
    fake_due.manual.add(4)  # relay 5
    communicator = connect()
    with pytest.raises(RelayControllerError, match="MANUAL") as excinfo:
        set_relay(communicator, 5, True)
    assert excinfo.value.code == 6


def test_status_reports_only_changes(fake_due):
    communicator = connect()
    first = communicator.read_available_packets()
    assert first[0]["type"] == "relay_states"
    assert first[0]["states"][1] is False
    assert communicator.read_available_packets() == []  # unchanged

    fake_due.states[1] = True  # e.g. relay switched by another path
    changed = communicator.read_available_packets()
    assert changed[0]["states"][2] is True


def test_status_reports_faults_and_manual(fake_due):
    fake_due.faults.add(0)
    fake_due.manual.add(7)
    packet = connect().read_available_packets()[0]
    assert packet["faults"] == [1]
    assert packet["manual"] == [8]


def test_silent_controller_raises_connection_error(fake_due):
    communicator = connect()
    communicator.read_available_packets()
    fake_due.silent = True
    communicator.max_missed_polls = 2
    assert communicator.read_available_packets() == []  # first miss tolerated
    with pytest.raises(ConnectionError):
        communicator.read_available_packets()


def test_release_all(fake_due):
    communicator = connect()
    set_relay(communicator, 2, True)
    time.sleep(0.01)
    communicator.release_all()
    assert not any(fake_due.states)


def test_missing_port_gives_plain_message():
    with pytest.raises(ValueError, match="devices.yaml"):
        PneumaticCommunicator().connect(port=None, baudrate=9600)
