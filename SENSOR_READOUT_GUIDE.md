# Generic Sensor Readout Panels

The `sensor_readout` dashboard panel is the generalized replacement for the
old temperature-only monitor.  It displays the most recent numeric value of any
enabled sensors defined in `config/sensors.yaml`.

A readout panel is a GUI consumer only:

```text
serial devices -> DeviceManager -> StreamHub -> QtDataBridge -> DataHub
                                                        |
                                                        +-> sensor_readout
```

It never opens a serial port and it does not create its own data thread.  This
means the same sensor can safely appear in a plot, the recorder, an automation
subscriber, and several readout panels at the same time.

## Basic dashboard YAML

```yaml
- id: controller_conditions
  type: sensor_readout
  title: Controller Conditions
  row: 2
  column: 0
  row_span: 1
  column_span: 1
  removable: true
  config:
    channels:
      - controller.temperature
      - controller.pressure_supply
      - controller.pressure_output
    columns: 2
    default_decimals: 1
    value_font_size: 24
    show_units: true
    show_source: false
    stale_after_s: 5.0
```

`channels` may mix physical quantities and source devices.  Their order in YAML
is the order used to build the cards.

## Multiple independent panels

Use a different `id` and grid position for each panel:

```yaml
- id: chamber_conditions
  type: sensor_readout
  title: Chamber
  row: 2
  column: 0
  config:
    channels:
      - controller.temperature
      - controller.pressure_output
    columns: 2

- id: room_conditions
  type: sensor_readout
  title: Room
  row: 2
  column: 1
  config:
    channels:
      - environment.temperature
      - environment.humidity
    columns: 2
```

The dashboard automatically expands when a new tile is placed in a new row or
column.  The Add Dashboard Panel dialog now defaults to the first free grid cell
instead of `(0, 0)`.

## Per-sensor display overrides

A tile may override presentation for individual sensors without changing the
project-wide `SensorDefinition`:

```yaml
config:
  channels:
    - controller.temperature
    - controller.pressure_supply
  default_decimals: 2
  display:
    controller.temperature:
      label: Board Temp
      decimals: 1
    controller.pressure_supply:
      label: Supply Pressure
      format: .4g
      font_size: 28
```

Supported per-channel keys are:

- `label`: tile-local display label
- `unit`: tile-local unit text
- `decimals`: fixed decimal places
- `format`: Python numeric format specification such as `.3f` or `.4g`
- `font_size`: value font size for that channel

If `format` is present it takes precedence over `decimals`.

A sensor may also set project-wide defaults in `sensors.yaml` metadata:

```yaml
controller.temperature:
  label: Controller Temperature
  source_device: controller
  source_channel: controller_temperature
  unit: °C
  enabled: true
  metadata:
    quantity: temperature
    display_decimals: 1
    display_format: .2f
```

Tile-local `display` overrides take precedence over sensor metadata.

## Legacy temperature monitor

Existing YAML using:

```yaml
type: temperature_monitor
```

continues to load.  `TemperatureMonitorTile` now subclasses the generic
`SensorReadoutTile`.  New panels should use `type: sensor_readout`.
