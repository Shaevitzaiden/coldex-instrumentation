"""Moved.

Instrument drivers are now plain files in src/pneumatic_valve_panel/drivers/
that are selected by name in config/devices.yaml. Start from:

    src/pneumatic_valve_panel/drivers/_template.py

and follow docs/ADDING_A_DEVICE.md.

Injecting objects directly is still possible for advanced use:

    run_app(..., communicators={"controller": MyCommunicator()})

where the key matches a device's communicator_key in devices.yaml.
"""
