# Configuration

The YAML files in this directory are the runtime configuration for the main PyQt application.

| File | Owns |
|---|---|
| `devices.yaml` | Hardware device definitions, enable flags, communicator keys, and connection parameters. |
| `actuators.yaml` | Authoritative logical actuator → physical device/relay bindings. |
| `sensors.yaml` | Normalized sensor IDs, labels, units, expected rates, and logging defaults. |
| `dashboard.yaml` | Saved dashboard layout, floating/closed state, and tile configuration. |
| `valve_panel.yaml` | Pneumatic panel geometry/elements. |

## Important ownership rule

Do not duplicate relay numbers in individual widgets. `actuators.yaml` is the single source of truth for relay bindings; widgets should reference logical `actuator_id` values.

## `devices.yaml`

Each device names a `driver` (list them with `python run_app.py --list-drivers`), its `connection` settings (COM port, baud rate), optional `options` for the driver, and an optional `demo_driver` used by `python run_app.py --demo`. A device that cannot connect is retried every `reconnect_interval_s` seconds and its reason is shown in the Device Connectivity tile.

Serial port names such as `COM14` are machine-specific. Review them on every new computer.

The `environment` device is **simulated**. Disable it once real sensors exist so fake values are not recorded.

To add an instrument, see [`docs/ADDING_A_DEVICE.md`](../docs/ADDING_A_DEVICE.md).

## `sensors.yaml`

The global sensor ID convention is:

```text
<source_device>.<logical_channel>
```

A communicator may emit local channel names; `DeviceWorker` maps them into these global IDs. Use `metadata.quantity` consistently (`pressure`, `temperature`, `flow_rate`, etc.) so compatible sensors can be grouped by dashboard widgets.

## `dashboard.yaml`

This file doubles as persistent user layout state. Floating panels, closed panels, and their geometry may therefore make it look different from the conceptual default layout described in feature guides. The current file has a fourth logical row because a floating panel was persisted there; empty/floating-only rows collapse visually.

For clean demo/reference layouts, prefer files in `examples/` rather than manually treating the saved dashboard as a factory default.
