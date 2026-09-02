# Crusher Control Dashboard Tile

The `crusher_control` tile controls four relay-driven pneumatic crushers through
the same `DeviceManager` and controller worker used by the pneumatic valve
panel. It does **not** open another serial connection.

## Physical state convention

The crusher hardware is extended when its solenoid is unpowered and retracts
when the solenoid is powered:

- **Up arrow (▲)** -> relay ON -> solenoid powered -> crusher raised/retracted
- **Down arrow (▼)** -> relay OFF -> solenoid unpowered -> crusher lowered/extended

By default `initialize_retracted: true`, so the tile queues an ON command for
each configured crusher when the application starts. Set it to `false` if you
do not want startup actuation.

## Dashboard YAML

```yaml
- id: crushers_main
  type: crusher_control
  title: Ice Crushers
  row: 2
  column: 0
  row_span: 1
  column_span: 2
  removable: true
  config:
    device_id: controller
    initialize_retracted: true
    crushers:
      - id: crusher_1
        label: Crusher 1
        relay_number: 17
      - id: crusher_2
        label: Crusher 2
        relay_number: 18
      - id: crusher_3
        label: Crusher 3
        relay_number: 19
      - id: crusher_4
        label: Crusher 4
        relay_number: 20
```

The relay numbers above are examples only. Use the physical relay assignments
for your hardware.

## Relay conflict handling

The tile checks its relay assignments against the current pneumatic valve-panel
configuration. If a crusher relay is also assigned to a valve-panel element,
that crusher's buttons are disabled and a warning is shown. Duplicate relay
assignments within the crusher tile are also disabled.

The Add/Configure Dashboard Panel dialog requires four unique relay numbers from
1 through 24. YAML-loaded invalid configurations are handled defensively at
runtime rather than sending commands.

## Command path

A button press follows this path:

```
CrusherControlTile
    -> DeviceManager.set_element_state(...)
    -> SerialDeviceService command queue
    -> controller DeviceWorker
    -> communicator.set_element_state(...)
    -> physical relay
```

The tile then waits for the worker's `CommandResult`, delivered through
`QtDataBridge -> DataHub.relay_result_received`, before marking the new state as
confirmed. This keeps GUI state changes asynchronous and prevents the widget
from touching the serial port directly.

## Shared controller

`device_id: controller` selects the same device service that the pneumatic valve
panel uses. Both widgets therefore serialize commands through the same command
queue and the same communicator-owning worker thread.
