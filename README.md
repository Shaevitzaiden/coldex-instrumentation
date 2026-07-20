# Barebones Pneumatic Valve Panel

This is a stripped-down, modular PyQt5 project that keeps only the useful part of the previous repo: a custom pneumatic valve control panel with round toggle buttons.

The GUI does **not** own serial ports and does **not** know anything about Arduino, firmware packets, sensors, data logging, autonomous routines, or plotting. Button clicks are routed through a small controller into an injected communicator object.

## What is included

```text
pneumatic_valve_panel_barebones/
  run_app.py
  config/
    valve_panel.yaml
  examples/
    my_communicator_template.py
  src/pneumatic_valve_panel/
    app.py
    main_window.py
    config_io.py
    models.py
    controllers/
      valve_controller.py
    serial/
      protocols.py
      demo_communicator.py
      adapters.py
    widgets/
      circular_valve_button.py
      valve_panel.py
```

## Install and run

From the repository root:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
python run_app.py
```

`run_app.py` uses `DemoCommunicator`, so it prints valve requests to the terminal instead of touching hardware.

## The important abstraction

Your serial layer only needs to provide this method:

```python
class MySerialCommunicator:
    def set_valve_state(
        self,
        *,
        valve_id: str,
        is_open: bool,
        command_id=None,
        metadata=None,
    ) -> None:
        # Send whatever packet your firmware expects here.
        pass
```

Then inject it into the app:

```python
from pathlib import Path
from pneumatic_valve_panel.app import run_app

communicator = MySerialCommunicator()
run_app(
    config_path=Path("config/valve_panel.yaml"),
    communicator=communicator,
)
```

The GUI sends:

```text
valve_id      Stable config id, e.g. "valve_01"
is_open       True for open/on, False for closed/off
command_id    Optional per-button command field from the YAML config
metadata      Optional per-button dictionary from the YAML config
```

In the included config, `command_id` is the legacy Arduino digital pin from the old project. You can replace it with any value your new communicator prefers.

## Editing the valve layout

The valve panel is config-driven. The example `config/valve_panel.yaml` is a cleaned-up version of the previous 21-button panel.

Use the GUI toolbar/menu:

1. Click **Edit Layout**.
2. Drag valve buttons to new positions.
3. Click **Save Layout** or press `Ctrl+S`.

The saved YAML stores each button center position.

## Config format

A minimal valve config looks like this:

```yaml
panel:
  title: My Valve Panel
  width: 900
  height: 500
  button_radius: 56

buttons:
  - id: valve_01
    label: "1"
    center: [100, 120]
    command_id: 2
    initially_open: false
    enabled: true
    metadata:
      manifold: A
      port: 1

lines:
  - orientation: h
    start: [50, 120]
    length: 300
    thickness: 16
```

Buttons can also define attached line segments that are drawn relative to the button center:

```yaml
attached_lines:
  - orientation: h
    length: 80
    thickness: 20
  - orientation: v
    length: -60
    thickness: 20
```

## Where to extend later

Useful extension points:

- Add additional windows in `main_window.py` or create new widgets under `widgets/`.
- Add new non-GUI state/services under `controllers/`.
- Keep serial/hardware code outside the widgets. The intended boundary is still `ValveController -> communicator.set_valve_state(...)`.
- If your communicator has an existing API, wrap it with an adapter in `serial/adapters.py` rather than changing the GUI.
