# Pneumatic Valve Panel Editor

This is a stripped-down, modular PyQt5 project focused on a custom pneumatic control panel. The GUI owns only layout editing and user interaction; your injected communicator owns all serial ports, packets, firmware protocol, retries, and hardware-specific behavior.

The core flow is:

```text
MainWindow
  application shell, menus, toolbars, docks, file actions

ValvePanelCanvas
  scalable runtime/editor canvas, drawing, hit testing, selection, pan/zoom,
  grid snapping, pipe creation, undo/redo, keyboard shortcuts

PropertiesPanel
  persistent selected-item editor dock

ValidationPanel
  relay binding validation and 24-relay browser dock

PneumaticController
  validates element IDs and forwards state requests to your communicator

Your serial communicator
  owns real hardware communication
```

The GUI never opens a serial port.

## Run

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
python run_app.py
```

`run_app.py` uses `DemoCommunicator`, which only prints requests to the terminal.

## Communicator API

The preferred generic API is:

```python
class MyCommunicator:
    def set_element_state(
        self,
        *,
        element_id: str,
        element_type: str,
        is_active: bool,
        relay_number: int | None = None,
        metadata: dict | None = None,
    ) -> None:
        # Send your serial command here.
        ...
```

The controller also supports the earlier barebones API:

```python
class MyCommunicator:
    def set_valve_state(
        self,
        *,
        valve_id: str,
        is_open: bool,
        command_id=None,
        metadata=None,
    ) -> None:
        ...
```

If both methods exist, `set_element_state(...)` is used.

## Runtime mode vs edit mode

The panel starts in **runtime mode**. In runtime mode:

```text
Click an enabled element       toggle it through the controller/communicator
Close/Deactivate All           send deactivate commands for all enabled elements
Layout editing controls        hidden
Hardware commands              enabled
```

Select **Edit Layout** to enter editor mode. In editor mode:

```text
Hardware toggle commands       disabled
Close/Deactivate All           hidden/disabled
Editor toolbar                 visible
Properties dock                visible
Validation / relay dock        visible
```

This keeps the normal control surface uncluttered and reduces accidental hardware activation while editing.

## Editor controls

```text
Ctrl+E            Toggle edit mode
Ctrl+Z / Ctrl+Y   Undo / redo layout edits
Ctrl+S            Save layout YAML
Ctrl+Shift+S      Save layout as
Ctrl+N            Add a new actuated element
Ctrl+P            Add pipes by clicking endpoints
Click             Select one element or pipe
Ctrl+click        Add/remove item from selection
Drag empty area   Box-select multiple items
Drag selection    Move selected items
Shift+drag        Constrain movement horizontally/vertically
Mouse wheel       Zoom the editor canvas
Middle-drag       Pan the editor canvas
Space+left-drag   Pan the editor canvas
R                 Rotate selected item(s) +90°
Shift+R           Rotate selected item(s) -90°
Delete/Backspace  Delete selected item(s)
Arrow keys        Nudge selected item(s)
Shift+arrow       Nudge selected item(s) by one grid step
Esc               Cancel pipe mode or clear selection
Ctrl+0            Fit canvas to window
```

## Implemented feature set in this version

This version implements the first group of suggested UX improvements:

1. **Undo / redo** for layout edits.
2. **Grid, snapping, and alignment tools** including show/hide grid, snap to grid, configurable spacing, align, distribute, arrow-key nudging, and constrained dragging.
3. **Multi-select editing** through Ctrl+click and rubber-band selection.
4. **Pan and zoom canvas** while in edit mode.
5. **Persistent properties panel** for selected elements and pipes.
6. **Relay binding validation** for missing, duplicate, and out-of-range relay assignments.
7. **Hardware binding browser** showing all 24 relays and whether each is available, assigned, or duplicated.
8. **Strict runtime/edit separation** so hardware commands are not triggered while editing.

## Relay validation

The Validation / Relay Browser dock checks:

```text
Relay binding is present or intentionally unbound
Relay number is within 1-24
Duplicate relay assignments
Unused relays
```

The relay browser shows all 24 relay channels and which element(s), if any, use each one.

## Scalable layout

The layout is stored in a fixed design coordinate system:

```yaml
panel:
  design_width: 1180
  design_height: 470
```

`ValvePanelCanvas` scales that coordinate system to the current widget size. In runtime mode it automatically fits the panel to the window. In edit mode you can pan and zoom the design canvas.

## Config structure

The main file is:

```text
config/valve_panel.yaml
```

Important sections:

```yaml
panel:
  title: Scalable Pneumatic Valve Panel Editor
  design_width: 1180
  design_height: 470
  default_element_size: [56, 56]
  background_color: "#f8f8f8"

valve_types:
  solenoid_2_way:
    display_name: 2-Way Solenoid Valve
    shape: circle
  solenoid_3_way:
    display_name: 3-Way Solenoid Valve
    shape: diamond
  selector_valve:
    display_name: Selector / Routing Valve
    shape: hexagon
  pneumatic_actuator:
    display_name: Pneumatic Actuator
    shape: rounded_rect
  pump_or_source:
    display_name: Pump / Pressure Source
    shape: triangle

elements:
  - id: valve_01
    label: "1"
    element_type: solenoid_2_way
    center: [32, 195]
    size: [56, 56]
    rotation: 0
    relay_number: 1
    initially_active: false
    enabled: true
    metadata: {}

pipes:
  - id: pipe_001
    start: [186, 100]
    end: [186, 300]
    thickness: 20
```

## Shapes

The built-in shapes are:

```text
circle
ellipse
rounded_rect
capsule
diamond
triangle
hexagon
rectangle fallback for unknown names
```

Add semantic element types in YAML under `valve_types`; the Add/Edit Element dialog and properties panel will automatically show them.

## Files to extend later

```text
src/pneumatic_valve_panel/main_window.py
  Application shell, menus, toolbar, docks, dialogs. Add future windows here or
  launch them from here.

src/pneumatic_valve_panel/widgets/valve_panel_canvas.py
  Scalable canvas, runtime toggles, editing interactions, undo/redo, grid,
  snapping, selection, deletion, rotation, pan/zoom, and pipe creation.

src/pneumatic_valve_panel/widgets/properties_panel.py
  Persistent selected-item property editor.

src/pneumatic_valve_panel/widgets/validation_panel.py
  Layout validation and 24-relay browser.

src/pneumatic_valve_panel/widgets/element_dialog.py
  Add/edit dialog for actuated elements, including element type and relay binding.

src/pneumatic_valve_panel/controllers/pneumatic_controller.py
  The only layer that talks to the injected communicator.

src/pneumatic_valve_panel/serial/
  Demo communicator, protocols, and adapter examples. Replace this with your own
  serial layer or add adapters here.
```
