# `pneumatic_valve_panel` package

Main desktop application package.

## Responsibility map

```text
app.py / app_context.py
    application construction and dependency wiring

main_window.py
    top-level PyQt window and dashboard management

hardware/
    DeviceManager + DeviceWorker thread ownership and command routing

drivers/
    named instrument drivers selected by `driver:` in devices.yaml
    (`_template.py` is the starting point for new ones)

serial/
    serial transport + relay-controller and demo communicators

actuators/
    central actuator registry and YAML binding persistence

data/
    data models, StreamHub, DataHub/Qt bridge, sensor configuration

controllers/
    higher-level control actions built on DeviceManager

recording/
    session logging/recording

widgets/
    dashboard, valve-panel and control widgets
```

## Hardware integration contract

A communicator should generally implement some combination of:

- `connect(...)`
- `disconnect()`
- `read_available_packets(timeout_s=...)` (or `read_packets`, `poll`, `read_packet`)
- hardware command methods called by `DeviceWorker`/controllers

For telemetry, returning a dict such as this is enough for `DeviceWorker` to normalize it:

```python
{
    "type": "sensor_frame",
    "sequence": 123,
    "device_timestamp": 42.125,
    "values": {
        "pressure": 1.23,
        "temperature": 21.8,
    },
}
```

`config/sensors.yaml` maps local keys such as `pressure` to global sensor IDs.

## Threading rule

**Only a device's worker thread should call its communicator.** GUI widgets must not directly open a port, perform blocking reads, or issue hardware calls. Commands flow through the DeviceManager command queue; telemetry flows through StreamHub.

## Adding the next instruments

Follow [`docs/ADDING_A_DEVICE.md`](../../docs/ADDING_A_DEVICE.md). The reference GRAPHIX and Adalogger drivers under `other/vacuum_instrumentation_bundle_v2/python/` should be wrapped as files in `drivers/`. LAUDA should follow the same pattern using a TCP socket. Agilent 7890A synchronization is better represented as digital/APG state and commands through the Due unless a supported Agilent software API is adopted.

## Connection handling

`DeviceWorker` never gives up on a device: a failed `connect()` is reported in the device status and retried every `reconnect_interval_s`. A `ConnectionError`/`OSError` (other than `TimeoutError`) raised while running is treated as a lost link and triggers a reconnect. Commands sent while a device is offline fail immediately so the GUI can undo the click.

## Valve state shown in the panel

The panel shows a valve's new state as soon as it is clicked, then corrects itself: a failed command restores the previous state, and the relay controller's once-a-second status report (`relay_states`) overrides any drift. This reflects what the controller is *driving*; there is no valve-position feedback.
