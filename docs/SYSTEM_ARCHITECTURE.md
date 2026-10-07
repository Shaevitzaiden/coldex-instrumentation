# System architecture

Updated: **2026-10-07**

This document distinguishes the physical laboratory system from what is currently wired into the desktop application.

## Whole-system control and acquisition diagram

```mermaid
flowchart TB
    Laptop[Main laptop\nPyQt GUI + logger\nAgilent software as needed]
    Hub[USB dock / hub]
    Switch[Ethernet switch / lab LAN]

    Due[Arduino Due\nmain relay controller]
    Relays[5 V relay modules]
    Pneumatics[24 V pneumatic valves\n+ other solenoids/crushers]

    Feather[Feather RP2040 Adalogger\n4-channel native ADC DAQ]
    GP475[Granville-Phillips / MKS 475]
    PDR[MKS PDR-D-1 + Baratron]

    RS232[USB ↔ true RS-232 adapter]
    Graphix[Leybold GRAPHIX]

    Lauda[LAUDA RP 290 E]
    GC[Agilent 7890A GC]
    AgilentSW[OpenLab / ChemStation]

    Laptop --- Hub
    Hub -->|USB serial| Due
    Due -->|3.3 V logic| Relays
    Relays -->|switch 24 V load circuits| Pneumatics

    Hub -->|USB CDC + power| Feather
    GP475 -->|0–7 V log analog| Feather
    PDR -->|0–10 V linear analog| Feather

    Hub -->|USB| RS232
    RS232 -->|straight-through RS-232| Graphix

    Laptop --- Switch
    Switch -->|Ethernet process interface| Lauda
    Switch -->|Ethernet| GC
    AgilentSW --> GC

    Due <-->|APG Remote sync\nplanned interface| GC
    GC -.->|optional SIG1/SIG2 analog| Feather
```

### Integration status of the diagram

- **Integrated now:** Due/relay control and the generic threaded device/data architecture.
- **Reference code exists but not injected into main app:** GRAPHIX and Feather analog DAQ.
- **Planned/documented:** LAUDA Ethernet communicator, GC APG Remote interface, optional GC analog monitor.

## Desktop data/control path

```mermaid
flowchart LR
    Widgets[Dashboard widgets] -->|DeviceCommand| Manager[DeviceManager]
    Manager --> Q1[Per-device command queue]
    Q1 --> Worker[DeviceWorker / QThread]
    Worker --> Comm[Communicator]
    Comm --> Hardware[Physical device]
    Hardware --> Comm
    Comm --> Worker
    Worker -->|SensorFrame / status / logs| Stream[StreamHub]
    Stream --> Recorder[SessionRecorder]
    Stream --> Bridge[Qt bridge / DataHub]
    Bridge --> Widgets
```

This architecture is intentionally device-agnostic. New instruments should be added as communicators rather than teaching widgets how to speak RS-232, TCP, or ADC protocols.

## Power architecture

The intended control-power topology is a **single 24 V DC bus** with local DC/DC conversion. Standalone laboratory instruments retain their normal mains power.

```mermaid
flowchart TB
    AC[AC mains] --> PSU[Mean Well HDR-150-24\n24 V main supply]
    PSU --> Bus[24 V distribution]
    Bus --> Valves[24 V valves / solenoids]
    Bus --> D12[Mean Well DDR-15G-12]
    Bus --> D5[Mean Well DDR-15G-5]
    D12 --> Due[Arduino Due VIN/barrel input]
    D5 --> RelayPower[5 V relay-coil / peripheral rail]

    Laptop[USB dock/laptop] -->|USB power| Feather[RP2040 Adalogger]
    Laptop -->|USB power| Adapter[USB-RS232 adapter]
```

The current BOM snapshot uses the **12 V DIN converter** for the Due; older notes that mention a 9 V Pololu converter are superseded by that choice.

## Analog DAQ channels

Baseline divider per 0–10 V channel:

```text
Instrument signal ---- 30.1 kΩ ----+---- Feather ADC (A0/A1/...)
                                   |
                                  10.0 kΩ
                                   |
Instrument return -----------------+---- Feather GND
                                   |
                                  100 nF
                                   |
                                  GND
```

Divider gain for reconstructing instrument voltage:

```text
Vin ≈ Vadc × (30.1k + 10.0k) / 10.0k = Vadc × 4.01
```

Current planned assignments:

| ADC | Source | Conversion |
|---|---|---|
| A0 | GP475 analog output | logarithmic pressure (`10^(V-4)` Torr in default 0–7 V/Torr mode) |
| A1 | PDR-D-1 `DC OUT` | linear pressure: `P = V/10 × full_scale` |
| A2 | spare / optional GC SIG1 | depends on GC configuration |
| A3 | spare / optional GC SIG2 | depends on GC configuration |

## Cable-routing intent

Physically separate these groups where possible:

```text
SIGNAL / LOW LEVEL             POWER / SWITCHED LOADS
------------------             ----------------------
GP475 analog                   24 V solenoid wiring
PDR-D-1 analog                 relay contact wiring
thermocouple                   valve-manifold wiring
USB/Ethernet                   high-current actuator wiring
```

Use through-bolted cable-tie bases / reusable strain relief at the edge-mounted USB dock, and leave service loops at connectors that users will plug/unplug.
