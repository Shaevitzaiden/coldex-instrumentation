# Project status / repository audit

Audit date: **2026-10-07**

## Executive status

The application is not obsolete. Its core architectural work — central actuator registry, per-device worker threads, StreamHub/DataHub, detachable dashboard tiles, and session recorder — is still a good foundation for the expanded instrumentation system.

The main gap is **integration drift**: newer hardware support has accumulated in design notes and `other/vacuum_instrumentation_bundle_v2`, while `run_app.py`, `config/devices.yaml`, and `config/sensors.yaml` still launch essentially the relay controller plus a demo environmental device.

## Subsystem status

| Subsystem | Status | Repository state / next action |
|---|---|---|
| PyQt dashboard | **Integrated** | Current fixed-grid/detachable dashboard architecture. |
| Central actuator registry | **Integrated** | `config/actuators.yaml` remains the authoritative relay mapping. |
| Arduino Due relay control | **Integrated / firmware refreshed** | Serial transport and firmware were cleaned during this audit. Hardware test still required after flashing. |
| MCP9601 thermocouple example | **Firmware refreshed, not main-app integrated** | Removed stale infinite diagnostic halt. A real host parser/device config still needs to be added if this sensor is used. |
| Leybold GRAPHIX | **Reference implementation** | Driver under `other/vacuum_instrumentation_bundle_v2/python/`; adapt to DeviceWorker interface and add to `devices.yaml`/`sensors.yaml`. |
| GP475 | **Reference implementation** | Analog conversion + Adalogger plan exist; not in main runtime config. |
| PDR-D-1 / Baratron | **Reference implementation** | Conversion exists; exact Baratron full-scale range remains required. |
| RP2040 Adalogger DAQ | **Reference firmware/driver** | Native-ADC design is baseline; ADS1115 design is optional. Not injected into main app. |
| LAUDA RP 290 E | **Pending integration** | Manufacturer supports Ethernet process control; add a TCP communicator/service and normalized temperature/status channels. |
| Agilent 7890A | **Pending synchronization integration** | Keep Agilent software as primary GC controller. Design/test APG Remote electrical interface to Due. Optional SIG analog monitoring is secondary. |
| 24/12/5 V power system | **Hardware/BOM design** | Current choice is HDR-150-24 + DDR-15G-12 + DDR-15G-5. Finalize total 24 V current and protection/distribution. |

## Code issues corrected in this audit

1. **Missing runtime dependency:** `pyserial` was imported but absent from both packaging dependency lists.
2. **False connection success:** `SerialCommunicator.connect()` swallowed `SerialException`, allowing the worker to report a failed serial port as connected. It now propagates the error.
3. **Broken read timeout:** the old code checked `in_waiting < 0`, a condition that cannot represent “waiting for bytes.” It now uses pyserial's timeout-driven line read.
4. **Broken serial smoke test:** removed the stale call to a nonexistent `num_bytes` argument.
5. **Ambiguous relay acknowledgements:** firmware debug prints could be mistaken for the command result. Firmware now sends only `1` or `0`; the host parser remains tolerant of older debug firmware during transition.
6. **First-command relay delay:** firmware timers now allow an immediate post-boot command.
7. **Thermocouple firmware halted forever:** removed the diagnostic `while (true)` after device-ID printing.
8. **Tests were not importable from repo root:** pytest now includes the nested vacuum-driver package path.
9. **Generated package/cache artifacts:** removed `*.egg-info`/`__pycache__` from the cleaned copy and expanded `.gitignore`.

## Configuration drift to be aware of

### Saved dashboard vs conceptual default

`config/dashboard.yaml` currently contains persisted user state:

- logical `rows: 4`, although the conceptual visible dashboard is still three main rows;
- `plot_main` saved floating/invisible;
- `tile_01` occupying its old docked area;
- a closed floating connectivity tile in row 3.

This is not necessarily corruption. Empty/floating-only rows collapse in the current dashboard manager. If you want a pristine distributable default configuration, create a separate example/default YAML rather than overwriting your saved working layout.

### Runtime hardware config

`config/devices.yaml` currently enables:

- `controller` → real `PneumaticCommunicator`
- `environment` → `DemoEnvironmentalCommunicator`

No GRAPHIX, Adalogger, LAUDA, or GC sync device is currently enabled/injected by `run_app.py`.

`config/sensors.yaml` currently enables only controller/environment temperature examples; most pressure/flow channels remain commented examples.

## Hardware/BOM items still needing explicit verification

- **24 V current budget:** record every valve/solenoid/actuator current before finalizing PSU margin and wire/protection sizes.
- **PDR-D-1:** record exact attached Baratron model and full-scale pressure.
- **Agilent APG Remote:** finalize the protected/optoisolated electrical interface before ordering/connecting it.
- **Relay module electrical interface:** exact Elegoo relay module revision/schematic is not yet pinned down. Verify 3.3 V input compatibility and whether `JD-VCC` genuinely provides the isolation behavior you intend.
- **24 V distribution:** the BOM snapshots in the repository predate the later discussion of using two 12-output Phoenix Contact PTFIX distribution blocks plus a bridge for a 24-output bus. Check the live procurement BOM before ordering.
- **5 V distribution:** verify the currently selected Phoenix distribution parts are the final choice after the later 3–4 output discussion.
- **Mains / branch protection:** distribution blocks are not overcurrent protection. The final physical build still needs protection appropriate to conductor/load ratings and the installation environment.

## Hardware documentation currency check

Manufacturer/source links were rechecked during this audit. The `docs/hardware/` index records the documents used and whether the source is manufacturer-hosted or an archive/mirror.

Notable points:

- Leybold still publishes the GRAPHIX English instruction manual from the current product page.
- MKS still publishes the Series 475 manual (Rev J, March 2020) for the legacy controller.
- LAUDA's current RP 290 E product pages still list the PRO Base operating instructions and Ethernet process-control capability.
- The 7890A is legacy equipment; use the 7890A-specific guides, and do not assume modern 8890/8860 commands apply.
- Agilent currently lists **7890A firmware A.01.16.1** as the latest 7890A release (September 2025). Treat this as a compatibility check, not an instruction to update a working GC without reviewing the firmware bulletin and your chromatography-software compatibility.

## Recommended next implementation sequence

1. Hardware-flash/test the cleaned Due relay firmware against `PneumaticCommunicator`.
2. Promote `AdaloggerDAQ` into the main package and define GP475/PDR sensors in YAML.
3. Promote `GraphixController` into the main package and add its pressure channels.
4. Implement/test a LAUDA TCP communicator.
5. Finalize the Agilent APG interface electrically, then add sync state/commands through the Due.
6. Only after those interfaces are stable, adjust the dashboard to expose all new channels/controls.
