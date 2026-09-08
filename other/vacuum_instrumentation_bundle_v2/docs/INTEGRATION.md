# Integration notes

## Recommended acquisition topology

- Leybold GRAPHIX -> USB-to-RS232 adapter -> laptop -> `GraphixController`
- GP475 -> divider/filter -> Feather A0
- PDR-D-1 -> divider/filter -> Feather A1
- Feather RP2040 Adalogger -> native USB CDC -> laptop -> `USBDaq`

Both native-ADC and optional ADS1115 firmware emit the same newline-delimited JSON sample format, so the Python host layer does not need to know which ADC implementation is installed.

## Why native ADC is the baseline
The pressure-controller outputs are slow, high-level analog signals. The Feather's four onboard RP2040 12-bit ADC channels provide enough practical resolution once the 0-10 V range is divided down. The external ADS1115 is therefore an accuracy/linearity/differential-input upgrade, not a functional requirement.

For the native implementation, use firmware averaging and calibrate gain/offset if measurement accuracy matters. Keep physical pressure conversion in Python so the DAQ firmware remains a generic voltage acquisition device.

## Data flow
Recommended host architecture:

`instrument driver/DAQ -> normalized Measurement -> DataHub -> GUI + logger + control logic`

Do not perform serial reads synchronously in the Qt GUI thread. Use a worker thread or asynchronous service and emit measurements/signals to the GUI.
