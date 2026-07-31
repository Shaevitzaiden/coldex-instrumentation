# Implementation Notes — v6.7 Fixed Grid

## Scope of the rollback

Only dashboard/window layout management was rolled back. The following newer systems remain intact:

- threaded `HardwareService` and command queue,
- `DataHub` broadcasting,
- live plots and sensor values,
- user/hardware log events,
- `SessionRecorder`, autosave, snapshots, and shutdown finalization,
- locked valve states and runtime context menus,
- valve-layout editor and valve-panel-local toolbars.

## Dashboard implementation

`widgets/tiles/dashboard_widget.py` is again a `QWidget` containing a `QGridLayout`, not a native dock manager.

The dashboard stores:

- `rows` and `columns`,
- `row_stretches` and `column_stretches`,
- one `DashboardTileConfig` per panel,
- explicit row/column and span geometry.

Runtime mode hides configure/remove buttons. Dashboard edit mode reveals them. Placement is validated before changes are applied; overlapping grid cells raise a user-visible error rather than allowing widgets to cover each other.

The default ratio is:

- columns `[3, 2]` → 60% / 40%,
- rows `[3, 1]` → 75% / 25%.

`DashboardConfig` still accepts legacy dock-state fields so old YAML can be parsed, but `DashboardWidget.current_config()` intentionally emits `dock_state=None` and `dock_layout_version="fixed_grid_v1"`.

## Singleton panels

The valve canvas and Session Recording widget are singleton application objects.

- `valve_panel_main` is non-removable.
- `recording_session` is non-removable.
- Resetting the dashboard temporarily reparents these two widgets, deletes the old dashboard, then inserts them into newly created tile wrappers.

The Session Recording widget is wrapped in a `QScrollArea`. This prevents its intrinsic size hint from forcing the bottom row above its configured 25% height while keeping every recording control accessible.

## Valve canvas resizing

The old design was `1180 × 470`, an aspect ratio that caused substantial vertical letterboxing in the new upper-left panel.

The packaged layout was transformed to `900 × 550`:

- X positions were multiplied by `900 / 1180`.
- Y positions were multiplied by `550 / 470`.
- Element dimensions were multiplied by `900 / 1180`, preserving approximately the same displayed button size at the new default fit.
- Pipe endpoints were transformed by the corresponding X/Y factors.

This changes the saved design coordinate system, not the canvas rendering algorithm. Runtime rendering continues to use uniform aspect-preserving fit.

## Dashboard edit interactions

`TileWidget` always displays its title. In dashboard edit mode it additionally shows:

- a configure button,
- a remove button for removable panels,
- a visual edit-mode header treatment.

The tile configuration dialog changes row, column, row span, column span, title, and tile-specific sensor options. Live plot and latest-value panels are rebuilt when their channel settings change. Valve, recording, and log panels are repositioned without replacing their live widget instances.

## Testing performed

- Python compile/AST parsing over the project.
- Dashboard YAML load/save round trip using the data-model modules without importing PyQt.
- Valve panel YAML load validation.
- Verification of the four default panel types and 3:2 / 3:1 stretch ratios.

PyQt5 is not installed in the artifact execution environment, so visual launch testing was not possible here.
