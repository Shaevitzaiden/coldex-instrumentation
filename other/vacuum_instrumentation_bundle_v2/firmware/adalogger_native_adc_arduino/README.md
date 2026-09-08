# Adalogger native-ADC firmware (recommended baseline)

This firmware uses the Feather RP2040 Adalogger's four onboard analog inputs A0-A3. No external ADC is required for the GP475 and PDR-D-1.

## Electrical front end per channel
- 30.1 kΩ ±0.1% from instrument output to ADC node
- 10.0 kΩ ±0.1% from ADC node to signal ground
- 100 nF X7R from ADC node to signal ground

The divider gain is 4.01, so 10 V at the instrument becomes about 2.494 V at the Feather. This leaves room for the GP475's ~10 V fault indication and prevents normal signals from approaching the 3.3 V ADC limit.

## Arduino setup
Select the Adafruit Feather RP2040 board/core as appropriate and upload `adalogger_native_adc_arduino.ino`. No extra ADC library is required.

## Calibration
The RP2040 ADC is adequate for these slow gauges but is not a precision metrology ADC. For better absolute voltage accuracy, apply at least a two-point calibration per channel using a reliable DMM and known input voltages. Edit `CAL_SCALE` and `CAL_OFFSET_V` in the sketch.

## USB commands
`PING`, `INFO`, `READ`, `START`, `STOP`, and `RATE <Hz>`.

The JSON sample format is intentionally identical to the ADS1115 firmware so the same Python host driver works with either implementation.
