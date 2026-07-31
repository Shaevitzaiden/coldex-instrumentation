# Implementation Notes — v6.8 Multi-Device Stream Hub

## Scope

The stable v6.7 fixed-grid GUI and valve editor were retained. The backend was refactored through migration phases 1–5:

1. source-qualified data models;
2. multiple independent device workers;
3. centralized thread-safe pub/sub;
4. recorder consumption and disk work moved to a background thread;
5. one live sensor tile may contain multiple plot axes.

## Phase 1: source-qualified frames

`SensorDefinition` now includes:

- `sensor_id`: globally qualified runtime ID;
- `source_device`;
- `source_channel`;
- label, unit, expected rate, and recording metadata.

`SensorFrame` now includes:

- `source_id`;
- `host_received_monotonic_ns`;
- global `elapsed_s` based on one application monotonic origin;
- host UTC time;
- device timestamp and sequence;
- values keyed by global sensor IDs.

The worker uses the sensor configuration to map local packet channels to global IDs. Unknown local channels receive a deterministic `<device_id>.<channel>` fallback.

## Phase 2: DeviceManager

The single `HardwareService` was replaced by:

- `DeviceManager`: lifecycle and command router;
- `SerialDeviceService`: queue/thread/worker owner for one device;
- `DeviceWorker`: communicator owner, packet parser boundary, and command executor.

Every enabled device receives one `QThread`. This isolates blocking instruments and guarantees one owner per serial port.

The old `HardwareService` and `HardwareWorker` import names remain aliases for migration compatibility, but new code should import `DeviceManager` and `DeviceWorker`.

`run_app()` accepts:

```python
communicators={"controller": controller, "flow_meter": meter}
```

The previous `communicator=controller` argument is still accepted and assigned to the configured command-target device.

## Phase 3: StreamHub

`StreamHub` has no Qt dependency. It provides:

- named topics;
- independent bounded subscriber queues;
- configurable overflow policy;
- latest-by-topic cache;
- latest value per sensor;
- latest frame per source;
- bounded per-sensor history;
- known-topic discovery.

Typed publishing helpers create topics for frames, per-channel samples, logs, command results, and device status.

`DataHub` is now only a GUI-thread cache and Qt signal facade. `QtDataBridge` drains StreamHub subscriptions on a timer and feeds DataHub. Full-rate consumers bypass that bridge.

## Phase 4: recorder worker

`SessionRecorder` is now a QObject facade around:

- a dedicated Python thread;
- frame and log StreamHub subscriptions;
- a recorder command queue;
- a pure `_RecorderState` file/persistence implementation.

Autosave and file writes occur in the recorder thread. Manual persistence commands first drain all frames/logs already queued before writing. Shutdown finalization blocks until the recorder confirms final files are complete.

The recorder uses a large bounded subscription. Overflow is logged as an error rather than allowing unbounded memory growth.

## Phase 5: multi-axis plotting

`LivePlotTile` accepts either:

- explicit `plot_groups`; or
- a flat channel list with `group_by_unit` enabled.

With pyqtgraph installed, a `GraphicsLayoutWidget` contains one `PlotItem` per group. Each channel has its own buffer/curve. Frames only append data; a 50 ms timer redraws the plots.

The fallback renderer creates one lightweight QWidget plot per group when pyqtgraph is unavailable.

## Thread ownership summary

```text
GUI thread
    MainWindow, ValvePanelCanvas, DataHub, QtDataBridge, plot widgets

One QThread per device
    communicator connect/read/write/disconnect, packet normalization

Recorder Python thread
    full-rate subscriptions, CSV/YAML writes, snapshots, autosave

Future automation threads
    direct StreamHub subscriptions and DeviceManager commands
```

## Tests performed

Because PyQt5 is not installed in the artifact environment, visual launch testing was not possible. The following checks were run:

- Python `compileall` across the complete project;
- device and sensor YAML loading;
- globally qualified local-channel normalization;
- multiple independent StreamHub subscriptions;
- latest-value and bounded-history queries;
- background recorder consumption from multiple source devices;
- separate per-sensor CSV creation and manifest finalization;
- archive content validation.

Minimal PyQt stubs were used only to load QObject-derived backend classes during non-visual tests; the actual project still depends on PyQt5 at runtime.
