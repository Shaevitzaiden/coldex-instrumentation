# Pneumatic Control Dashboard — Multi-Device Stream Architecture

A modular PyQt5 application for pneumatic relay control, synchronized sensor acquisition, multi-axis live plotting, terminal-style logging, and recoverable recording sessions.

This version retains the stable fixed-grid dashboard from v6.7 while implementing the backend migration phases 1–5:

1. globally qualified sensor/source identifiers;
2. independently threaded serial devices;
3. a centralized thread-safe producer/consumer `StreamHub`;
4. background recording that consumes directly from the hub;
5. multiple live plot axes inside one sensor panel.

## Default fixed layout

```text
┌───────────────────────────────┬─────────────────────┐
│ Pneumatic Valve Panel         │ Live Sensor Plots   │
│ approximately 60% width       │ approximately 40%   │
│ approximately 75% height      │ matching height     │
├───────────────────────────────┼─────────────────────┤
│ System Log                    │ Session Recording   │
│ approximately 25% height      │ approximately 25%   │
└───────────────────────────────┴─────────────────────┘
```

Runtime panel positions are fixed. **Edit Dashboard Layout** exposes explicit row, column, and span configuration without native Qt docking.

## High-level architecture

```text
Multiple serial devices
├── controller communicator + DeviceWorker/QThread
├── environment communicator + DeviceWorker/QThread
└── future instruments, each with its own worker
                │
                ▼
             StreamHub
      ┌─────────┼──────────────┐
      │         │              │
      ▼         ▼              ▼
Recorder   QtDataBridge   Future automation
(full rate) (rate limited)  subscribers
                │
                ▼
             DataHub
      ┌─────────┼───────────┐
      ▼         ▼           ▼
Live plots  value table  log window
```

Commands travel in the opposite direction:

```text
ValvePanelCanvas / future automation
              │
              ▼
      PneumaticController
              │
              ▼
         DeviceManager
              │ addressed DeviceCommand
              ▼
      target device command queue
              │
              ▼
        device communicator
```

Only the worker assigned to a device touches that device's serial communicator.

## Running the demonstration

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run_app.py
```

The packaged launcher injects two independent simulated devices:

- `controller`: relay commands, pressure, flow, and controller temperature at 20 Hz;
- `environment`: ambient temperature and humidity at 5 Hz.

They demonstrate that one plot panel, the recorder, latest-value widgets, and future consumers can all observe data from multiple sources.

## Configuring devices

`config/devices.yaml` defines independently managed devices:

```yaml
devices:
  controller:
    enabled: true
    communicator_key: controller
    command_target: true
    connection:
      port: COM4
      baudrate: 921600
      timeout_s: 0.05

  flow_meter:
    enabled: true
    communicator_key: flow_meter
    command_target: false
    connection:
      port: COM6
      baudrate: 115200
```

The YAML does not instantiate drivers. Inject live communicator objects in Python:

```python
run_app(
    config_path=ROOT / "config" / "valve_panel.yaml",
    device_config_path=ROOT / "config" / "devices.yaml",
    communicators={
        "controller": ControllerCommunicator(...),
        "flow_meter": FlowMeterCommunicator(...),
    },
)
```

Each enabled device receives:

- one `DeviceWorker`;
- one `QThread`;
- one outgoing command queue;
- one communicator owner;
- a local-channel-to-global-sensor mapping.

## Configuring sensors

`config/sensors.yaml` uses globally qualified IDs:

```yaml
sensors:
  controller.pressure_supply:
    label: Supply Pressure
    source_device: controller
    source_channel: pressure_supply
    unit: kPa
    expected_sampling_hz: 20

  flow_meter.flow:
    label: Flow Rate
    source_device: flow_meter
    source_channel: flow
    unit: L/min
    expected_sampling_hz: 50
```

The device driver can emit local names such as `pressure_supply`. The worker maps them into `controller.pressure_supply` before publishing. This prevents collisions when two devices both expose a channel named `temperature`.

## Preferred incoming packet format

```python
{
    "type": "sensor_frame",
    "sequence": 123,
    "device_timestamp": 4.250,
    "values": {
        "pressure_supply": 551.2,
        "pressure_output": 125.8,
    },
}
```

All channels in `values` remain one synchronized `SensorFrame` with:

- `source_id`;
- global application elapsed time;
- host UTC receive time;
- host monotonic nanoseconds;
- optional device timestamp;
- optional sequence number;
- globally qualified value IDs.

## StreamHub producer/consumer behavior

`StreamHub` is a non-Qt, thread-safe broker. Every subscriber has its own bounded queue, so a plot, recorder, and automation consumer all receive the same data instead of competing to remove messages from one shared queue.

Useful topics include:

```text
frames/controller
frames/flow_meter
sensors/controller.pressure_supply
logs/application
logs/devices.controller
commands/results/controller
devices/status/controller
```

Example consumer:

```python
subscription = stream_hub.subscribe(
    "frames/controller",
    queue_size=1000,
    overflow_policy="drop_oldest",
    name="pressure-automation",
)

envelope = subscription.get(timeout=0.1)
frame = envelope.payload
pressure = frame.values["controller.pressure_supply"]
```

Synchronous queries are also available:

```python
latest = stream_hub.latest_value("controller.pressure_supply")
history = stream_hub.history("controller.pressure_supply")
topics = stream_hub.list_topics()
```

Overflow policies are selected per consumer:

- `drop_oldest`: appropriate for plots;
- `replace_latest`: appropriate for status widgets;
- `drop_newest`: preserve already queued work;
- `block`: recorder-oriented, with finite timeout and overflow reporting.

## GUI bridge

`QtDataBridge` is the only component that converts the central streams into GUI signals. It drains bounded subscriptions on a timer so raw acquisition rates do not generate one Qt cross-thread signal per sample.

The recorder does **not** use the bridge. It subscribes directly to `StreamHub` at full rate.

## Background recording

`SessionRecorder` now owns a dedicated Python worker thread. That thread:

- consumes `frames/*` and `logs/*` directly from `StreamHub`;
- writes one CSV and metadata YAML per selected global sensor ID;
- preserves common timestamps for values from the same frame;
- performs periodic autosaves;
- creates non-terminating snapshots;
- drains already-published frames before manual saves and finalization;
- writes final data during normal shutdown.

A sensor CSV includes:

```text
timestamp_utc
elapsed_s
value
sequence
device_timestamp
host_received_monotonic_ns
source_device
```

## Multiple plots in one sensor panel

A live plot tile now uses `pyqtgraph.GraphicsLayoutWidget` and may hold several vertically stacked axes.

Explicit grouping in `config/dashboard.yaml`:

```yaml
plot_groups:
  - title: Pressures
    unit: kPa
    channels:
      - controller.pressure_supply
      - controller.pressure_output

  - title: Temperatures
    unit: °C
    channels:
      - controller.temperature
      - environment.temperature
```

Channels from different devices can share an axis when they use compatible units. If `plot_groups` is omitted, `group_by_unit: true` automatically creates separate axes for pressure, flow, temperature, and other units.

## Important source files

```text
src/pneumatic_valve_panel/data/stream_hub.py
    Thread-safe publish/subscribe broker, subscriptions, caches, history.

src/pneumatic_valve_panel/data/qt_bridge.py
    Rate-limited StreamHub-to-Qt bridge.

src/pneumatic_valve_panel/hardware/device_manager.py
    DeviceManager, per-device QThreads/workers, packet normalization,
    command routing.

src/pneumatic_valve_panel/recording/session_recorder.py
    Background recorder facade, worker loop, incremental persistence.

src/pneumatic_valve_panel/widgets/tiles/live_plot_tile.py
    Multi-axis buffered plotting panel.

config/devices.yaml
    Device lifecycle and communicator-key configuration.

config/sensors.yaml
    Global sensor definitions and local-channel mappings.
```

## Extending toward automation

Automation is intentionally not implemented in this phase, but the backend is ready for it. An automation worker should:

1. subscribe directly to `StreamHub`;
2. maintain its own queue/overflow policy;
3. inspect immutable frames or samples;
4. submit addressed commands through `DeviceManager` rather than touching a communicator or GUI widget.

See `examples/stream_consumer_example.py`.
