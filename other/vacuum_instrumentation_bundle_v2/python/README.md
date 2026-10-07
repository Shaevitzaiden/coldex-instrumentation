# Vacuum instrumentation Python reference drivers

This directory is a **reference integration package**, not yet part of the main `pneumatic_valve_panel` runtime package.

## Modules

- `vacuum_instruments/graphix.py` — direct Leybold GRAPHIX RS-232 protocol driver.
- `vacuum_instruments/usb_daq.py` — USB JSON protocol for the Feather RP2040 Adalogger firmware.
- `vacuum_instruments/analog.py` — GP475 and PDR-D-1 voltage→pressure conversion functions.
- `examples/` — bench/smoke-test scripts.
- `tests/` — conversion/protocol unit tests.

## Install / test

From the repository root, the main `pyproject.toml` now exposes the nested package to pytest:

```bash
pip install -e ".[dev]"
pytest -q
```

For a standalone bench environment you can also install `python/requirements.txt` directly.

## Promotion into the main GUI

Do not call these blocking drivers from a widget. Adapt them to the main package's `DeviceWorker` communicator contract so each instrument owns its connection in one worker thread and publishes normalized sensor packets through StreamHub.
