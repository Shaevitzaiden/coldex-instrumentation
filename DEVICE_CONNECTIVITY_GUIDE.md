# Device Connectivity Dashboard Tile

The `device_connectivity` tile is a GUI-only diagnostic consumer. It does not
open, close, or poll serial ports; `DeviceManager` remains the exclusive owner
of hardware lifecycle and serial I/O.

Add it through **Edit Dashboard Layout -> Add Dashboard Panel -> Device
connectivity**, or with YAML:

```yaml
- id: device_connectivity
  type: device_connectivity
  title: Device Connectivity
  row: 2
  column: 0
  row_span: 1
  column_span: 2
  removable: true
  config: {}
```

For every device in `config/devices.yaml`, the table displays:

- device ID and role (command target vs peripheral/data device);
- connected/disconnected/disabled state from `DeviceStatus`;
- configured serial port;
- configured baud rate;
- age of the most recent normalized sensor frame;
- GUI-observed frame rate over a rolling window;
- detected positive sequence-number gaps.

The data path is:

```text
DeviceWorker
   -> StreamHub devices/status/* and frames/*
   -> QtDataBridge
   -> DataHub
   -> DeviceConnectivityTile
```

A device may legitimately show `Connected` and `No data` if it is command-only
or does not publish sensor frames.

## Optional YAML configuration

The normal dialog displays every configured device. Advanced YAML may restrict
the table or change the frame-rate window:

```yaml
config:
  devices:
    - controller
    - thermocouple_board
  rate_window_s: 10
```

`rate_window_s` is only a GUI diagnostic window. Full-rate recording and future
automation still consume `StreamHub` directly.
