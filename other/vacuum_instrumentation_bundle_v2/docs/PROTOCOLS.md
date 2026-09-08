# Protocol summary

## Leybold GRAPHIX
Host is master. RS-232: ASCII messages, 8-N-1, no hardware handshake. Control bytes: SI=0x0F read, SO=0x0E write, ACK=0x06, NACK=0x15, EOT=0x04, separator `;`.

Read frame: `[SI]group;parameter CRC[EOT]`.
CRC byte = `255 - (sum(all preceding bytes) mod 256)`; if result < 32, add 32.
Read response: `[ACK]value CRC[EOT]` or `[NACK]error CRC[EOT]`.
Pressure channels are groups 1,2,3; parameter 29 is rounded/corrected pressure with unit. Group 5 parameter 1 is hardware/software version and is a useful communications smoke test.

## Adalogger USB DAQ
Included firmware uses newline-delimited JSON over native USB serial. Example:
`{"type":"sample","t_us":123456,"volts":[4.000001,5.000002,0.0,0.0]}`
Commands: PING, INFO, READ, START, STOP, RATE <0.2..25>.

## GP475 conversion
Default 0–7 V log mode: Torr or mbar: `P=10^(V-4)`; Pa: `P=10^(V-2)`. A 10 V output indicates unplugged/faulty gauge. Optional 1–8 V mode shifts exponent by -1. S-curve mode is intentionally not implemented in the Python helper.

## PDR-D-1 conversion
For a correctly configured 0–10 V full-scale Baratron readout: `P = (V/10) * P_full_scale`. Confirm the actual Baratron full-scale range/nameplate before logging engineering units.
