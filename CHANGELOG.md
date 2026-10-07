# Changelog

## 2026-10-07 — robustness and add-in structure

- Relay firmware **protocol v2**: `<I>` identity, `<?>` status, `<X>` release-all, `0,<code>` error codes, strict parsing, output-pin readback, repeated-state commands exempt from the 100 ms lockout, optional communication-loss fail-safe (`COMMS_TIMEOUT_MS`, off) and switch-panel AUTO/MANUAL hook (`SWITCH_PANEL_INSTALLED`, off). **Not yet compiled or flashed.**
- `PneumaticCommunicator`: identity handshake with boot wait, readable error messages, status polling that reports relay-state changes, lost-link detection after 3 missed polls.
- `DeviceWorker`: retries failed connections every `reconnect_interval_s`, reconnects after a lost link, fails commands immediately while offline.
- Valve panel: failed commands restore the previous state; controller status reports correct any drift (e.g. after a controller reset) and are logged as warnings.
- Drivers are selected by name in `devices.yaml` (`driver:`, `demo_driver:`, `options:`); new driver files in `src/pneumatic_valve_panel/drivers/` load automatically. Added `LineSerialSensor` base class, `mcp9601_thermocouple` driver, `_template.py`, and `docs/ADDING_A_DEVICE.md`.
- `run_app.py --demo` (all devices simulated, marked in the window title) and `--list-drivers`.
- `tools/relay_bench.py` for manual relay tests without the dashboard.
- New `tests/` suite (23 tests) including a Python model of the relay firmware.
- Marked the `environment` device and `controller.temperature` sensor as simulated/demo-only in config.

## 2026-10-07 — repository audit / documentation refresh

- Added root/config/firmware/package/docs README documentation.
- Added whole-system architecture and power/data-flow diagrams.
- Added project-status audit distinguishing integrated vs reference/pending hardware.
- Added hardware-manual source manifest and downloader under `docs/hardware/`.
- Added missing `pyserial` runtime dependency and pytest development configuration.
- Fixed generic serial connection reporting and timeout behavior.
- Simplified relay-controller protocol to deterministic `1`/`0` acknowledgements.
- Removed stale relay debug output and fixed first-command switch-delay behavior.
- Removed the thermocouple firmware's diagnostic infinite loop.
- Removed generated cache/package-metadata directories from the cleaned repository.
