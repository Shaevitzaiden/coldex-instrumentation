# Arduino Due relay controller

Firmware: `relay_controls.ino` — **protocol v2**. The desktop app checks the
protocol version on connect, so re-flash this sketch whenever it changes.

Flash with the Arduino IDE: *Tools → Board → Arduino Due (Programming Port)*,
using the Due's **programming** USB port (the one nearest the DC jack).

## Pin map

Three 8-channel relay modules are mapped to 24 Due pins:

| Module | Due pins | Firmware relay index | Relay number in `actuators.yaml` |
|---|---|---|---|
| 1 | 22–29 | 0–7 | 1–8 |
| 2 | 32–39 | 8–15 | 9–16 |
| 3 | 42–49 | 16–23 | 17–24 |

## Electrical assumption

The relay inputs are **active-low**:

- Due output `LOW` → relay energized / requested state `1`
- Due output `HIGH` → relay released / requested state `0`

All relays are released at power-up and after every reset. Opening the
programming port from the PC usually resets the Due, so starting the desktop
app releases every relay.

## Serial protocol (9600 baud)

Every message is framed `<...>`; every reply is one line. Lines starting with
`#` are notes for humans and are ignored by the app.

| Send | Reply | Meaning |
|---|---|---|
| `<n,s>` | `1` / `0,<code>` | Set relay index n (0–23) to s (0 off, 1 on) |
| `<?>` | `S,<states>,<modes>` | 24 characters each. States: `1` on, `0` off, `E` readback fault. Modes: `A` auto, `M` manual |
| `<I>` | `I,coldex_relay_controller,2,24` | Identity / protocol version / channel count |
| `<X>` | `1` | Release every relay immediately (ignores the lockout) |

Error codes: `1` malformed, `2` index out of range, `3` state not 0/1,
`4` switched again within 100 ms, `5` output pin readback mismatch,
`6` channel in MANUAL on the switch panel, `7` unknown command.

You can test by hand in the Arduino Serial Monitor (9600 baud, any line
ending): type `<I>`, `<?>`, `<4,1>`, `<X>`.

Or from the repository root, with the desktop app closed:

```text
python tools/relay_bench.py COM14
```

## Built-in checks

- **Strict parsing** — a frame must be exactly `index,state` with digits only.
- **Lockout** — one relay cannot change state twice within 100 ms. Repeating
  the state a relay is already in is always accepted.
- **Pin readback** — after switching, the firmware reads the output pin back.
  This catches a shorted or damaged pin. It cannot tell whether the relay
  clicked or the valve moved.
- **Communication-loss fail-safe** (off by default) — set `COMMS_TIMEOUT_MS`
  to release all relays when the PC stops talking. The app polls every second.

## Switch panel (not yet installed)

Set `SWITCH_PANEL_INSTALLED = true` and list one sense pin per relay in
`AUTO_SENSE_PINS` (`-1` = no switch). Each sense pin uses `INPUT_PULLUP`; the
switch's spare pole should connect the pin to **Due GND** when the switch is
in AUTO. An open pin reads as MANUAL and the firmware refuses automated
commands on that channel (error `6`). Never connect a sense pin to 5 V or 24 V.

Free Due pins that avoid the relay outputs, USB serial and I²C include
2–13, 30–31, 40–41, 50–53 and A0–A11.
