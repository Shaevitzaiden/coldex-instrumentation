# Feather RP2040 Adalogger firmware variants

## Recommended baseline

`adalogger_native_adc_arduino/`

Uses the Feather's A0–A3 RP2040 ADC inputs with the documented 30.1 kΩ / 10.0 kΩ divider and 100 nF input filter. This is sufficient for the slow 0–10 V-class pressure-controller outputs and avoids an unnecessary external ADC.

## Alternatives

- `adalogger_native_adc_circuitpython/` — same front end in CircuitPython.
- `adalogger_ads1115_arduino/` — optional ADS1115 path for higher resolution/differential acquisition.
- `adalogger_ads1115_circuitpython/` — ADS1115 alternative in CircuitPython.

All variants are intended to expose a compatible newline-delimited JSON command/sample protocol so host code can remain mostly independent of the ADC implementation.
