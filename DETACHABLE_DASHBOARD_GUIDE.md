# Detachable dashboard panels

The operational dashboard remains a deterministic `QGridLayout`. It does **not**
return to Qt's native `QDockWidget` splitter system.

Every `TileWidget` has a `↗` button in its title bar:

- `↗` removes the tile from the grid and reparents the **same widget instance**
  into an ordinary top-level `DetachedTileWindow`.
- `↙` returns it to the main dashboard.
- Closing a detached window with the normal OS **X** closes/hides that panel; it does **not** redock it.
- `↙` is the only action that returns a floating panel to the main dashboard.
- Closed floating panels can be restored with **Dashboard → Reopen Closed Panel…**.

Because a floating tile is not counted when `DashboardWidget` checks occupied
cells, another panel may be placed in the cells it vacated. If the detached
panel is later returned and those cells are occupied, the dashboard searches for
the next free location with the same row/column span. It grows the grid when
necessary rather than overlap another panel.

## Spawn a panel directly as a window

Use **Dashboard → Spawn Floating Panel…** or `Ctrl+Shift+F`. This opens the same
configuration dialog used by Add Dashboard Panel, but the resulting tile is
created with `floating: true` immediately. No dashboard-edit-mode or temporary
grid placement is required.

Its stored row/column are merely the preferred location if it is later redocked.
New floating windows are slightly cascaded so several spawned panels do not open
exactly on top of one another.

## Persistence

`DashboardTileConfig` supports:

```yaml
floating: true
visible: false   # present when a floating panel has been closed/hidden
floating_geometry: [x, y, width, height]
```

A panel closed with the window-manager X keeps its configuration and last
floating geometry but does not occupy grid cells or create a top-level window.
Saving the dashboard preserves `visible: false`; use **Reopen Closed Panel…** to
make it visible again.

`DashboardWidget.current_config()` captures the geometry of every floating
window. Moving or resizing a detached window marks the dashboard dirty, so
**Save Dashboard Layout** persists its current location. On the next launch,
tiles saved with `floating: true` are recreated directly as separate windows.

If the saved monitor arrangement is unavailable, the window is placed near the
main application instead of restoring completely off-screen.

## Default 8-column × 3-row layout

```text
columns:   0   1   2   3 | 4   5 | 6   7
          +---------------+-------+-------+
row 0     |               |       |       |
          |  Pneumatic    | Live  |Session|
row 1     |  Valve Panel  | Plots |Record.|
          |               |       |       |
          +---------------+-------+       |
row 2     | Ice Crushers  |Sensor |       |
          |               |Cards  |       |
          +---------------+-------+-------+
```

- Pneumatic Valve Panel: `(row=0, column=0, row_span=2, column_span=4)`
- Ice Crushers: `(2, 0, 1, 4)`
- Live Sensor Plots: `(0, 4, 2, 2)`
- Sensor Values: `(2, 4, 1, 2)`
- Session Recording: `(0, 6, 3, 2)`

The terminal log, device connectivity, extra plots, and other tiles can be added
to new grid rows or spawned directly as separate windows.

## Floating panels no longer create empty dashboard rows

Panels created with **Dashboard -> Spawn Floating Panel...** keep a preferred
redock row/column, but those coordinates do not expand the live main-window
grid until the panel is actually redocked.  Likewise, when the last docked
panel leaves a row, that row's stretch becomes zero so it does not leave dead
space at the bottom of the dashboard.  The logical row count is still retained
in `dashboard.yaml` for later redocking/layout editing.
