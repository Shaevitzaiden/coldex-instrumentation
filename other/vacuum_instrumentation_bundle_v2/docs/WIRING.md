# Wiring reference — v2 native-ADC baseline

## 1. Leybold GRAPHIX — direct RS-232
Use the rear **RS232/RS485** DB9 and a **straight-through, shielded** serial extension plus a real USB-to-RS232 adapter.

GRAPHIX DB9:
- pin 2 = TxD (RS-232)
- pin 3 = RxD (RS-232)
- pin 5 = GND

Typical/default communication is 38400 baud, 8 data bits, no parity, 1 stop bit, no hardware handshake. Do **not** use a TTL-UART cable and do **not** use a null-modem cable/adapter.

## 2. Native Adalogger four-channel 0-10 V front end
The Feather's ADC pins are 3.3 V-domain inputs, so every 0-10 V instrument channel needs attenuation.

Per populated channel:

```
Instrument signal ---- 30.1 kΩ 0.1% ----+---- Feather A0/A1/A2/A3
                                         |
                                       10.0 kΩ 0.1%
                                         |
Instrument signal ground ----------------+---- Feather GND
                                         |
                                        100 nF
                                         |
                                        GND
```

Divider gain from ADC voltage back to instrument voltage:

`(30.1k + 10.0k) / 10.0k = 4.01`

Important points:
- 10.0 V instrument output -> ~2.494 V at the Feather ADC.
- ~13.23 V instrument output would reach ~3.30 V at the ADC.
- This gives useful headroom around the GP475's approximately 10 V fault indication.
- Divider input resistance is ~40.1 kΩ, which is above the PDR-D-1's specified 10 kΩ minimum load.
- 100 nF provides simple low-pass/noise filtering together with the divider impedance.

Populate CH0/A0 and CH1/A1 for the current system; CH2/A2 and CH3/A3 are optional spares.

### Calibration
The RP2040 ADC is sufficient for these slow gauge outputs, but the 3.3 V reference/supply and ADC transfer function are not laboratory-grade references. For better absolute accuracy, apply two known input voltages (ideally spanning the normal range), measure them with a good DMM, and set per-channel gain/offset constants in firmware.

Firmware averaging reduces random noise. It does not eliminate deterministic ADC nonlinearity.

## 3. Granville-Phillips 475001-00-T
Use the rear analog-output 1/8-inch (3.5 mm) miniature phone jack. Verify the connector wiring against the exact unit/manual before energizing the DAQ connection.

Recommended configuration:
- output mode: **1 V/decade, 0-7 V**
- programmed analog-output offset: preferably 0 V

Reference assignment:
- GP475 analog signal -> divider -> Feather A0
- GP475 analog return -> Feather GND

The GP475 can indicate a gauge fault/disconnection with an output near 10 V; the native-ADC divider is designed to accommodate this without approaching the Feather's 3.3 V input ceiling.

## 4. MKS PDR-D-1
Use the rear terminal strip:
- **DC OUT** -> divider -> Feather A1
- **S GND** -> Feather GND

Do not substitute P GND for S GND unless the exact wiring/manual requires it. The PDR-D-1 DC OUT is nominally 0-10 V and requires a load impedance of 10 kΩ or greater; the ~40.1 kΩ divider satisfies this.

Pressure conversion requires the full-scale range of the attached Baratron.

## 5. Grounding
This reference DAQ is **not isolated**. Once connected, instrument signal grounds are tied through the Feather and laptop USB ground. Before connecting multiple line-powered instruments, measure for unexpected DC/AC potential between their signal grounds. If ground-loop current/noise appears, use isolation or a commercial isolated DAQ rather than trying to solve it only in software.

## Suggested channel assignment
- A0 / CH0 = GP475 analog output
- A1 / CH1 = PDR-D-1 DC OUT
- A2 / CH2 = spare
- A3 / CH3 = spare
