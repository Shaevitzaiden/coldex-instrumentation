# Firmware

Firmware for locally controlled embedded hardware.

## `relay_controls/`

Target: **Arduino Due** used as the main pneumatic/solenoid relay controller.
Protocol **v2**: identity handshake, status query, all-off, error codes, pin
readback, optional switch-panel AUTO/MANUAL sensing and an optional
communication-loss fail-safe. Full protocol, pin map and flashing notes:
[`relay_controls/README.md`](relay_controls/README.md).

The desktop driver is `src/pneumatic_valve_panel/serial/pneumatic_communicator.py`
(registered as driver `relay_controller`). `tests/fake_relay_firmware.py` is a
Python model of the sketch used by the tests; keep the two in step.

## `thermocouple_reader/`

Example MCP9601 K-type thermocouple firmware using `PWFusion_Mcp960x`.

- I2C: 100 kHz
- Serial: 9600 baud
- Normal sample: one floating-point temperature in °C per line
- Error codes: 15 startup, 16 open circuit, 17 short circuit, 18 pending/non-ready

The 2026-10-07 audit removed a leftover diagnostic infinite loop that previously prevented `loop()` from ever running.

Desktop driver: `mcp9601_thermocouple` (`src/pneumatic_valve_panel/drivers/mcp9601_thermocouple.py`). Enable the `thermocouple` device in `config/devices.yaml` and set its COM port.

## Vacuum DAQ firmware

The RP2040 Adalogger firmware is kept with its matching host drivers and documentation in:

```text
other/vacuum_instrumentation_bundle_v2/firmware/
```

The **native ADC** version is the baseline design. The ADS1115 version is retained as an optional higher-resolution alternative.
