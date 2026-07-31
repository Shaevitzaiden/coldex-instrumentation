# Pneumatic Control Dashboard

A modular PyQt5 application for pneumatic relay control, synchronized live-sensor display, terminal-style logging, and recoverable sensor-recording sessions.

## v6.7 layout rollback

The operational dashboard no longer uses native Qt docking. Native docks proved too unpredictable for a four-panel control interface, particularly when nested, resized, or rearranged.

The application now uses a stable grid-backed dashboard:

```text
┌───────────────────────────────┬─────────────────────┐
│ Pneumatic Valve Panel         │ Live Sensor Plot    │
│ approximately 60% width       │ approximately 40%   │
│ approximately 75% height      │ matching height     │
├───────────────────────────────┼─────────────────────┤
│ System Log                    │ Session Recording   │
│ approximately 25% height      │ approximately 25%   │
└───────────────────────────────┴─────────────────────┘
```

The default proportions are stored in `config/dashboard.yaml` as:

```yaml
row_stretches: [3, 1]
column_stretches: [3, 2]
```

In normal operation, panel positions are fixed. **Edit Dashboard Layout** (`Ctrl+D`) reveals configure/remove controls on panel headers. Tile geometry is changed explicitly through row, column, row-span, and column-span values, so panels cannot disappear beneath one another or produce unstable splitter trees.

The valve-layout editor remains separate from dashboard editing. Valve controls and valve-editing actions remain attached to the valve panel itself.

## Default valve canvas

The valve design canvas is now `900 × 550`, matching the aspect ratio of the default upper-left dashboard region more closely. Existing valve and pipe coordinates were rescaled so the default runtime zoom uses the available vertical space rather than letterboxing the previous `1180 × 470` design.

## Features retained

- Configurable pneumatic valve/actuator panel with relay bindings 1–24.
- Runtime right-click actions for toggle and lock/unlock.
- Locked-state color muting and lock icon.
- Valve-layout undo/redo, selection, add/edit/delete, rotation, pipes, snapping, and alignment.
- Valve-specific runtime and editing controls embedded in the valve panel.
- One threaded hardware service that owns the injected communicator.
- Thread-safe relay command queue.
- Synchronized multi-channel sensor frames.
- Buffered live plots using `pyqtgraph`, with a simple fallback renderer.
- Terminal-style application and hardware log stream.
- Selectable per-sensor recording.
- Separate CSV and metadata files per sensor.
- Session folders named by date/time.
- Periodic autosave, manual save, non-terminating snapshots, and save-and-close.
- Final log and sensor-data flush during normal shutdown.

## Running

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run_app.py
```

The included `DemoCommunicator` generates sample data and prints relay requests without requiring hardware.

## Main configuration files

- `config/valve_panel.yaml` — valve types, valve elements, pipes, positions, relay bindings, and initial states.
- `config/dashboard.yaml` — fixed-grid panel placement and row/column proportions.
- `config/sensors.yaml` — sensor labels, units, expected sampling frequencies, and default logging choices.

## Dashboard editing

1. Select **Edit Dashboard Layout** or press `Ctrl+D`.
2. Use the gear button on a panel to change its row, column, or span.
3. Add optional plot, latest-value, or log panels from the Dashboard menu.
4. Remove optional panels using their edit-mode remove button.
5. Save with **Save Dashboard Layout**.
6. Use **Reset Dashboard Layout** to restore the packaged 60/40 by 75/25 four-panel arrangement.

The valve panel and Session Recording panel are non-removable because they own singleton application widgets. Plot and log panels may be removed or added.

## Hardware communicator boundary

The preferred outgoing method is:

```python
def set_element_state(
    self,
    *,
    element_id: str,
    element_type: str,
    is_active: bool,
    relay_number: int | None = None,
    metadata: dict | None = None,
) -> None:
    ...
```

The hardware worker also accepts incoming packets from methods such as `read_packet()`, `read_message()`, `receive()`, or `poll()`.

A synchronized sensor frame should resemble:

```python
{
    "type": "sensor_frame",
    "sequence": 123,
    "device_timestamp": 4.250,
    "values": {
        "pressure_supply": 551.2,
        "pressure_output": 125.8,
        "flow_rate": 2.1,
    },
}
```

Every channel in one frame receives the same host UTC timestamp and elapsed time.

## Recorded session structure

```text
recorded_sessions/
└── 2026-07-31_10-30-00/
    ├── system_log.csv
    ├── session_manifest.yaml
    ├── pressure_supply__Supply_Pressure.csv
    ├── pressure_supply__Supply_Pressure_metadata.yaml
    └── snapshots/
```

Sensor metadata includes the configured label, unit, expected sampling frequency, estimated sampling frequency, sample count, start/end timestamps, and elapsed duration.
