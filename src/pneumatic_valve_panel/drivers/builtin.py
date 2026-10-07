"""Registers the drivers that ship with the application."""

from ..serial.demo_communicator import DemoCommunicator, DemoEnvironmentalCommunicator
from ..serial.pneumatic_communicator import PneumaticCommunicator
from . import register_driver

register_driver(
    "relay_controller",
    description="Arduino Due pneumatic relay controller (firmware/relay_controls, protocol v2)",
)(PneumaticCommunicator)

register_driver(
    "demo_controller",
    description="SIMULATED relay controller with fake pressure/flow telemetry",
)(DemoCommunicator)

register_driver(
    "demo_environment",
    description="SIMULATED ambient temperature/humidity sensor",
)(DemoEnvironmentalCommunicator)
