# Changelog

## v2
- Changed recommended analog acquisition from ADS1115 to the Feather RP2040 Adalogger's onboard ADCs.
- Added native-ADC Arduino and CircuitPython firmware while preserving the existing JSON USB protocol.
- Changed analog divider to 30.1 kΩ / 10.0 kΩ, giving a 4.01 reconstruction gain and ~2.494 V ADC input at 10 V instrument output.
- Retained ADS1115 implementation as an optional upgrade path.
- Reworked BOM structure by shared analog DAQ, GP475, PDR-D-1, GRAPHIX RS-232, and optional upgrades.
- Added direct purchase links and current approximate prices.

## v1
- Initial GRAPHIX serial, analog DAQ, conversion helpers, wiring notes, and BOM.
