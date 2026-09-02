# Central Actuator Registry

`config/actuators.yaml` is the authoritative mapping from a logical actuator
name to a physical hardware output.  New GUI and automation code should never
own a relay number independently.

```text
Pneumatic element -----\
                        -> actuator_id -> ActuatorRegistry -> device + relay
Crusher control -------/                        |
                                                 -> DeviceManager -> device worker
Future automation -----/
```

## Definition schema

```yaml
actuators:
  valve_01:
    label: Inlet Valve
    kind: solenoid_2_way
    device_id: controller
    relay_number: 1
    enabled: true
    default_active: false
```

Important fields:

- `actuator_id`: YAML key and stable global logical name.
- `device_id`: an entry from `config/devices.yaml`.
- `relay_number`: physical output on that device.
- `kind`: semantic type used for diagnostics/logging.
- `enabled`: disabled placeholders may remain unbound without validation errors.
- `default_active`: descriptive startup/default state for higher-level logic.
- `metadata`: actuator-specific semantic information.

The registry validates edited bindings against configured device IDs, relay
range, and every other actuator.  Relay swaps/multi-actuator edits are applied
atomically, so a rejected edit cannot leave a half-created registry entry.

## Pneumatic panel binding

`config/valve_panel.yaml` now contains:

```yaml
- id: valve_01
  actuator_id: valve_01
  ...
```

It does **not** contain a relay number. In valve-layout edit mode, both the
Add/Edit Element dialog and the Properties panel edit the referenced actuator's
Device and Relay fields in the central registry.  The canvas annotation resolves
and shows the live registry binding dynamically.

Changing a binding therefore affects every subsequent command immediately; the
pneumatic widget does not need to be rebuilt.

## Crusher binding

Crusher dashboard configuration also stores only logical IDs:

```yaml
crushers:
  - id: crusher_1
    label: Crusher 1
    actuator_id: crusher_1
```

The Crusher Controls configuration dialog edits the corresponding central
registry definitions.  Crusher and valve relay assignments are validated in the
same operation, so they cannot silently claim the same physical output.

## Global validation

The valve editor's **Validation / Relay Browser** now contains an **Actuator
Registry** tab showing every configured device/relay and its logical owner.
Validation reports:

- duplicate physical bindings;
- out-of-range relay numbers;
- enabled actuators with no relay;
- actuator definitions referencing unknown devices;
- pneumatic elements referencing missing actuator IDs;
- multiple pneumatic elements referencing the same logical actuator.

## Persistence and dirty state

Actuator edits have their own dirty state.  **Save Valve Layout** and **Save
Dashboard Layout** both persist `config/actuators.yaml` when necessary.  Closing
or loading another layout prompts for unsaved valve/actuator changes.

## Backward compatibility

Older `valve_panel.yaml` files containing `relay_number` and older crusher
dashboard configs containing `device_id`/`relay_number` are migrated in memory
at load time.  The next save writes the new actuator-ID schema and
`actuators.yaml`.  Historical conflicts are preserved during migration so the
validation UI can explain them instead of silently choosing a different relay.

## Command API

New widgets and automation should prefer:

```python
device_manager.set_actuator_state(
    actuator_id="valve_01",
    is_active=True,
    metadata={"origin": "automation.example"},
)
```

`DeviceManager` resolves the current registry binding immediately before the
command is queued.  Do not pass physical relays from new application code.
`set_element_state()` remains only as a lower-level/backward-compatible API for
external integrations and the final communicator boundary.
