# Combined live plot + current-value tile

The dashboard now supports a reusable tile type:

```yaml
type: sensor_plot_readout
```

It is intended for several comparable sensor channels that should share one
live y-axis while also showing their current values as large text above the
plot. Typical examples are multiple temperatures, multiple pressures, or
multiple strain channels.

## Why channels must be one measurement group

One `sensor_plot_readout` tile has one y-axis. The selected sensors must
therefore have the same physical quantity **and the same unit**. For example:

- `controller.temperature` and `environment.temperature` in °C: valid.
- two pressure channels in kPa: valid.
- temperature + pressure: rejected.
- °C + °F: rejected until a unit-conversion layer is added.

The preferred way to classify sensors is in `config/sensors.yaml`:

```yaml
controller.temperature:
  label: Controller Temperature
  source_device: controller
  source_channel: controller_temperature
  unit: °C
  metadata:
    quantity: temperature
```

Known units are also recognized as a backwards-compatible fallback, but
`metadata.quantity` is clearer and scales to project-specific sensor types.

## Example dashboard tile

```yaml
- id: temperatures_with_plot
  type: sensor_plot_readout
  title: Temperatures
  row: 2
  column: 0
  row_span: 1
  column_span: 2
  removable: true
  config:
    channels:
      - controller.temperature
      - environment.temperature
    quantity: temperature
    unit: °C
    y_label: Temperature
    history_seconds: 60
    readout_columns: 2
    default_decimals: 1
    value_font_size: 20
    show_units: true
    show_source: true
    stale_after_s: 5
```

The `quantity`, `unit`, and `y_label` fields are written by the configuration
dialog for clarity. The tile still defensively validates the actual channel
definitions when it is constructed, so manually edited YAML cannot silently
combine incompatible curves.

## Per-sensor text formatting

As with `sensor_readout`, optional display overrides can be supplied:

```yaml
    display:
      controller.temperature:
        label: Controller
        decimals: 1
      environment.temperature:
        label: Room
        format: .2f
```

## Data path

The tile consumes the same broadcast `DataHub.frame_received` signal as the
other GUI visualizations:

```text
DeviceWorker -> StreamHub -> QtDataBridge -> DataHub
                                      -> sensor_plot_readout
                                      -> live_plot
                                      -> sensor_readout
```

It does not remove data from any other consumer. The same sensor can therefore
be plotted, shown as text, recorded, and consumed by future automation logic at
the same time.
