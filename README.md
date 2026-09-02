# Pneumatic Control Dashboard

This revision keeps the fixed-grid dashboard and multi-device StreamHub
architecture while adding a central actuator registry shared by every
relay-driven control surface.

## Central actuator registry

`config/actuators.yaml` is the authoritative mapping from logical actuator IDs
to physical `device_id + relay_number` bindings. Pneumatic valve elements and
crusher controls store only `actuator_id`; the current physical binding is
resolved when a command is queued.

This prevents separate widgets from independently claiming the same relay and
means changing one actuator binding updates every command producer at once.
See `ACTUATOR_REGISTRY_GUIDE.md`.

## Device connectivity tile

`type: device_connectivity` provides a passive hardware-health table for every
device in `config/devices.yaml`. It reports role, connection state, configured
port/baud, latest telemetry age, observed frame rate, and detected sequence
gaps. It consumes existing `DataHub` messages and never opens or polls serial
ports itself. See `DEVICE_CONNECTIVITY_GUIDE.md`.

## Combined plot + numeric sensor tile

`type: sensor_plot_readout` combines a live one-axis plot with current-value
cards for multiple compatible sensors. Use `metadata.quantity` in
`config/sensors.yaml` to classify sensor channels. The Add Dashboard Panel
dialog exposes a Measurement Group selector and only permits sensors with the
same quantity and unit. See `SENSOR_PLOT_READOUT_GUIDE.md` and
`examples/sensor_plot_readout_dashboard_examples.yaml`.

## Generic numeric readout tile

`type: sensor_readout` displays arbitrary configured sensor values as live
numeric cards. Multiple readout tiles may coexist and may group mixed quantities
when that is useful for one subsystem. See `SENSOR_READOUT_GUIDE.md`.

## Crusher control tile

`type: crusher_control` adds four side-by-side Up/Down controls for relay-driven
pneumatic crushers. The tile references four logical actuator IDs from the
central registry, shares the existing controller DeviceManager worker, waits for
command results before confirming state, and can request startup retraction.
Relay uniqueness is enforced centrally by `ActuatorRegistry`, rather than by
widget-to-widget conflict checks. See `CRUSHER_CONTROL_GUIDE.md` and
`examples/crusher_control_dashboard_example.yaml`.
