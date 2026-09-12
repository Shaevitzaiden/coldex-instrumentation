# 8-column equipment layout and direct floating panels

This revision changes only dashboard presentation/launch behavior; StreamHub,
DeviceManager, actuator routing, recording, sensor tiles, and command workers
remain unchanged.

## Main layout

The shipped dashboard is 8 columns × 3 rows. Pneumatics occupy 4×2, crushers are
4×1 underneath, the middle two columns are sensor visualization space, and the
right two columns are Session Recording across all three rows.

## Direct floating creation

`MainWindow._spawn_floating_dashboard_tile()` uses `TileConfigDialog`, then sets
`DashboardTileConfig.floating = True` before calling `DashboardWidget.add_tile`.
The normal `DashboardWidget._float_tile()` path therefore creates the same
`DetachedTileWindow` used when a docked panel's `↗` button is pressed.

This means a directly spawned window has the same persistence semantics as a
manually detached tile:

- it participates in `dashboard.yaml`;
- its geometry is saved;
- it is restored as a top-level window on launch;
- it can be redocked later;
- it consumes no grid cells while floating.

Shortcut: `Ctrl+Shift+F`.

## Compact recording rail

`RecordingPanel` keeps the same controls and functionality, but now uses a
compact browse toolbutton, shorter labels, shortened visible sensor names, and
header resize modes that reserve width for the sensor-name column. Full sensor
IDs and source information remain in tooltips.
