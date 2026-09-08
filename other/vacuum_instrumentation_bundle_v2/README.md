# Vacuum Instrumentation Integration Bundle v2

Reference code, wiring, and purchasing information for:
- Leybold GRAPHIX gauge controller via RS-232
- Granville-Phillips 475001-00-T via analog output
- MKS PDR-D-1 via analog DC output
- Adafruit Feather RP2040 Adalogger used directly as a low-cost four-channel USB analog DAQ

## What changed in v2
The external ADS1115 is now **optional**, not part of the baseline design. The Feather RP2040 Adalogger already exposes four onboard 12-bit ADC channels (A0-A3), which are adequate for these slow pressure-controller outputs when used with a resistor divider, RC filter, firmware averaging, and calibration.

The ADS1115 examples are retained as an upgrade path if later measurements need a more stable reference, better linearity/resolution, differential acquisition, or additional analog-performance margin.

## Recommended baseline hardware
One Feather RP2040 Adalogger acquires both analog instruments:
- A0 <- Granville-Phillips 475 analog output through 30.1k/10.0k divider
- A1 <- MKS PDR-D-1 DC OUT through 30.1k/10.0k divider
- A2/A3 <- spare 0-10 V channels

Each populated channel also gets 100 nF from the ADC node to signal ground.

The GRAPHIX remains a separate direct RS-232 connection to the laptop.

## Quick start
1. See `docs/WIRING.md` and build the native-ADC divider/filter front end.
2. Flash `firmware/adalogger_native_adc_arduino/adalogger_native_adc_arduino.ino` (recommended baseline). No ADS1115 library is needed.
3. Install Python dependencies: `pip install -r python/requirements.txt`.
4. Test GRAPHIX with `python/examples/graphix_smoketest.py`.
5. Set the DAQ COM port and PDR Baratron full-scale value in your application/example.
6. Calibrate the analog channels against a DMM if absolute voltage accuracy matters.

## BOM
- `bom/BOM.xlsx`: grouped, formatted BOM with separate sheets for the analog DAQ core, GP475, PDR-D-1, GRAPHIX RS-232, and optional upgrades.
- `bom/BOM.csv`: flat version with the same group labels and product URLs.

Prices are snapshots and will change. Cable lengths are installation dependent.

## Important configuration checks
- GRAPHIX: confirm RS-232 mode/baud and use a straight-through DB9 cable. Do not use TTL UART or a null-modem adapter/cable.
- GP475: confirm analog output is 1 V/decade, 0-7 V and preferably zero programmed offset.
- PDR-D-1: identify the attached Baratron and enter its actual full-scale range in software.
- Homemade DAQ: non-isolated. Check inter-instrument ground potential before tying signal grounds together.

## Firmware folders
- `firmware/adalogger_native_adc_arduino/` — recommended, no external ADC
- `firmware/adalogger_native_adc_circuitpython/` — same electrical design in CircuitPython
- `firmware/adalogger_ads1115_arduino/` — optional higher-performance ADC path
- `firmware/adalogger_ads1115_circuitpython/` — optional higher-performance ADC path

## Sources
See `docs/SOURCES.md` and the purchase URLs in the BOM.

## Scope
This is reference integration code, not a certified measurement or safety system. Confirm connector pinouts and instrument configuration against the exact hardware/manual before wiring.
