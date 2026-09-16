from __future__ import annotations

from collections.abc import Iterable

from PyQt5 import QtCore, QtWidgets

from ...data.models import DashboardConfig, DashboardTileConfig
from .tile_base import TileWidget


class DetachedTileWindow(QtWidgets.QMainWindow):
    """Top-level host for one detached dashboard tile.

    The window-manager close button means "close/hide this floating panel".
    It deliberately does *not* redock the tile.  Redocking is reserved for the
    explicit ↙ control in the tile header, which keeps those two user actions
    semantically distinct.
    """

    close_requested = QtCore.pyqtSignal(str)
    geometry_changed = QtCore.pyqtSignal(str)

    def __init__(self, tile_id: str, title: str) -> None:
        super().__init__(None)
        self.tile_id = tile_id
        self._allow_close = False
        self._close_pending = False
        self._geometry_notifications_enabled = False
        self.setWindowTitle(title)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, False)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        if self._allow_close:
            event.accept()
            return

        # Avoid modifying/reparenting the central widget from inside Qt's own
        # closeEvent. Ignore this event and let DashboardWidget perform the
        # close/hide operation on the next event-loop turn.
        event.ignore()
        if not self._close_pending:
            self._close_pending = True
            QtCore.QTimer.singleShot(0, lambda: self.close_requested.emit(self.tile_id))

    def enable_geometry_notifications(self) -> None:
        # Geometry is restored before the first show.  Enabling notifications
        # afterward prevents a restored layout from being marked dirty simply
        # because Qt applies its saved size/position.
        self._geometry_notifications_enabled = True

    def moveEvent(self, event) -> None:  # noqa: N802 - Qt API name
        super().moveEvent(event)
        if self._geometry_notifications_enabled:
            self.geometry_changed.emit(self.tile_id)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        super().resizeEvent(event)
        if self._geometry_notifications_enabled:
            self.geometry_changed.emit(self.tile_id)

    def force_close(self) -> None:
        """Close the top-level host without emitting a user close request."""

        self._allow_close = True
        self.close()


class DashboardWidget(QtWidgets.QWidget):
    """Fixed grid dashboard with optional detached top-level panel windows.

    This intentionally does *not* use QDockWidget.  Qt's native dock splitter
    tree was the source of the earlier overlap/collapse behavior.  The main
    window therefore stays a deterministic QGridLayout while any tile may be
    moved into its own ordinary top-level window.

    A floating tile remains in ``tiles`` and ``tile_configs`` but does not
    occupy grid cells. This is what allows another panel to be placed in the
    vacated space. Its original/current grid coordinates are retained as the
    preferred redock location. A floating tile can additionally be *closed*
    (``visible=False``): it remains in the saved layout but has no top-level
    window until explicitly reopened.
    """

    tile_removed = QtCore.pyqtSignal(str)
    tile_configure_requested = QtCore.pyqtSignal(str)
    layout_changed = QtCore.pyqtSignal()

    def __init__(
        self,
        *,
        rows: int = 2,
        columns: int = 2,
        row_stretches: Iterable[int] | None = None,
        column_stretches: Iterable[int] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.rows = max(1, int(rows))
        self.columns = max(1, int(columns))
        self.row_stretches = self._normalized_stretches(row_stretches, self.rows, default=1)
        self.column_stretches = self._normalized_stretches(column_stretches, self.columns, default=1)
        self.tiles: dict[str, TileWidget] = {}
        self.tile_configs: dict[str, DashboardTileConfig] = {}
        self.floating_windows: dict[str, DetachedTileWindow] = {}
        self._edit_mode = False

        self.grid = QtWidgets.QGridLayout(self)
        self.grid.setContentsMargins(6, 6, 6, 6)
        self.grid.setHorizontalSpacing(6)
        self.grid.setVerticalSpacing(6)
        self._update_stretch()

    @staticmethod
    def _normalized_stretches(
        values: Iterable[int] | None,
        count: int,
        *,
        default: int,
    ) -> list[int]:
        result = [max(0, int(value)) for value in (values or [])]
        if len(result) < count:
            result.extend([default] * (count - len(result)))
        return result[:count]

    # ------------------------------------------------------------------
    # Placement helpers
    # ------------------------------------------------------------------
    def first_free_cell(self, *, row_span: int = 1, column_span: int = 1) -> tuple[int, int]:
        """Return the first location where a tile of this span will fit.

        Floating tiles intentionally do not count as occupied.  If the current
        grid is full, a new row is returned; ``add_tile`` expands the grid when
        the tile is actually inserted.
        """

        return self._first_free_position(row_span=max(1, row_span), column_span=max(1, column_span))

    def _first_free_position(self, *, row_span: int, column_span: int) -> tuple[int, int]:
        # If a requested tile is wider than the configured grid, expand the
        # conceptual column count before searching.
        if column_span > self.columns:
            self.columns = column_span
            self.column_stretches.extend([1] * (self.columns - len(self.column_stretches)))
            self._update_stretch()

        # Search current rows first.
        max_start_row = max(self.rows - row_span, 0)
        max_start_column = max(self.columns - column_span, 0)
        for row in range(max_start_row + 1):
            for column in range(max_start_column + 1):
                probe = DashboardTileConfig(
                    tile_id="__placement_probe__",
                    tile_type="probe",
                    title="",
                    row=row,
                    column=column,
                    row_span=row_span,
                    column_span=column_span,
                )
                if self._placement_available(probe):
                    return row, column

        # Existing rows are full.  Append enough rows for this tile.
        return self.rows, 0

    def _placement_available(
        self,
        config: DashboardTileConfig,
        *,
        exclude_tile_id: str | None = None,
    ) -> bool:
        if config.floating or not config.visible:
            return True
        desired = self._occupied_cells(config)
        for tile_id, existing in self.tile_configs.items():
            if tile_id == exclude_tile_id or existing.floating or not existing.visible:
                continue
            if desired.intersection(self._occupied_cells(existing)):
                return False
        return True

    # ------------------------------------------------------------------
    # Tile lifecycle
    # ------------------------------------------------------------------
    def add_tile(self, tile: TileWidget, config: DashboardTileConfig, *, emit_change: bool = True) -> None:
        if config.tile_id in self.tiles:
            raise ValueError(f"A dashboard tile named {config.tile_id!r} already exists")

        # Floating-only preferred return coordinates must not resize the live
        # dashboard.  The grid expands only when the panel is actually docked.
        if config.visible and not config.floating:
            self._ensure_grid_contains(config)
        self._validate_placement(config)
        self.tiles[config.tile_id] = tile
        self.tile_configs[config.tile_id] = config
        self._wire_tile(tile, config)

        if not config.visible:
            # Closed panels stay alive/configured but occupy neither the grid
            # nor a top-level window.  This is especially important for the
            # singleton valve/recording widgets, which must not be destroyed.
            tile.setParent(self)
            tile.hide()
        elif config.floating:
            self._float_tile(config.tile_id, geometry=config.floating_geometry, emit_change=False)
        else:
            self._add_tile_to_grid(tile, config)

        if emit_change:
            self.layout_changed.emit()

    def _wire_tile(self, tile: TileWidget, config: DashboardTileConfig) -> None:
        tile.set_title(config.title)
        tile.set_dashboard_edit_mode(self._edit_mode)
        tile.set_floating_state(config.floating)
        tile.close_requested.connect(self.remove_tile)
        tile.configure_requested.connect(self.tile_configure_requested.emit)
        tile.floating_toggle_requested.connect(self.toggle_tile_floating)

    def _add_tile_to_grid(self, tile: TileWidget, config: DashboardTileConfig) -> None:
        self.grid.addWidget(
            tile,
            max(0, config.row),
            max(0, config.column),
            max(1, config.row_span),
            max(1, config.column_span),
        )
        tile.show()
        self._update_stretch()

    @QtCore.pyqtSlot(str)
    def remove_tile(self, tile_id: str, *, emit_change: bool = True) -> None:
        tile = self.tiles.get(tile_id)
        config = self.tile_configs.get(tile_id)
        if tile is None or config is None or not config.removable:
            return

        self.tiles.pop(tile_id, None)
        self.tile_configs.pop(tile_id, None)

        if config.floating:
            window = self.floating_windows.pop(tile_id, None)
            if window is not None:
                central = window.takeCentralWidget()
                if central is not None:
                    central.setParent(None)
                window.force_close()
                window.deleteLater()
        else:
            self.grid.removeWidget(tile)

        tile.deleteLater()
        self._update_stretch()
        self.tile_removed.emit(tile_id)
        if emit_change:
            self.layout_changed.emit()

    def replace_tile(
        self,
        tile_id: str,
        replacement_tile: TileWidget,
        replacement_config: DashboardTileConfig,
    ) -> None:
        old_tile = self.tiles[tile_id]
        old_config = self.tile_configs[tile_id]
        replacement_config.tile_id = tile_id
        replacement_config.tile_type = old_config.tile_type
        replacement_config.removable = old_config.removable

        # Reconfiguration should not implicitly dock/undock a panel.  That is
        # controlled only by the ↗/↙ button or closing the detached window.
        replacement_config.floating = old_config.floating
        replacement_config.visible = old_config.visible
        replacement_config.floating_geometry = self._floating_geometry(tile_id)

        if not replacement_config.floating:
            self._ensure_grid_contains(replacement_config)
        self._validate_placement(replacement_config, exclude_tile_id=tile_id)

        self.tiles[tile_id] = replacement_tile
        self.tile_configs[tile_id] = replacement_config
        self._wire_tile(replacement_tile, replacement_config)

        if not old_config.visible:
            replacement_tile.setParent(self)
            replacement_tile.hide()
        elif old_config.floating:
            window = self.floating_windows[tile_id]
            old_central = window.takeCentralWidget()
            window.setCentralWidget(replacement_tile)
            window.setWindowTitle(replacement_config.title)
            if old_central is not None:
                old_central.setParent(None)
        else:
            self.grid.removeWidget(old_tile)
            self._add_tile_to_grid(replacement_tile, replacement_config)

        old_tile.deleteLater()
        self.layout_changed.emit()

    def update_tile_config(self, tile_id: str, replacement: DashboardTileConfig) -> None:
        tile = self.tiles[tile_id]
        old = self.tile_configs[tile_id]
        replacement.tile_id = tile_id
        replacement.tile_type = old.tile_type
        replacement.removable = old.removable
        replacement.floating = old.floating
        replacement.visible = old.visible
        replacement.floating_geometry = self._floating_geometry(tile_id)

        if not replacement.floating:
            self._ensure_grid_contains(replacement)
        self._validate_placement(replacement, exclude_tile_id=tile_id)
        self.tile_configs[tile_id] = replacement
        tile.set_title(replacement.title)

        if not replacement.visible:
            tile.hide()
        elif replacement.floating:
            window = self.floating_windows.get(tile_id)
            if window is not None:
                window.setWindowTitle(replacement.title)
        else:
            self.grid.removeWidget(tile)
            self._add_tile_to_grid(tile, replacement)

        self.layout_changed.emit()

    # ------------------------------------------------------------------
    # Detach / reattach
    # ------------------------------------------------------------------
    @QtCore.pyqtSlot(str)
    def toggle_tile_floating(self, tile_id: str) -> None:
        config = self.tile_configs.get(tile_id)
        if config is None:
            return
        if not config.visible:
            self.reopen_tile(tile_id)
        elif config.floating:
            self.redock_tile(tile_id)
        else:
            self._float_tile(tile_id, geometry=config.floating_geometry, emit_change=True)

    def _float_tile(
        self,
        tile_id: str,
        *,
        geometry: list[int] | None,
        emit_change: bool,
    ) -> None:
        tile = self.tiles[tile_id]
        config = self.tile_configs[tile_id]
        if tile_id in self.floating_windows:
            self.floating_windows[tile_id].raise_()
            self.floating_windows[tile_id].activateWindow()
            return

        self.grid.removeWidget(tile)
        window = DetachedTileWindow(tile_id, config.title)
        window.close_requested.connect(self.close_floating_tile)
        window.geometry_changed.connect(self._on_floating_geometry_changed)
        window.setCentralWidget(tile)
        self.floating_windows[tile_id] = window

        config.floating = True
        config.visible = True
        tile.set_floating_state(True)
        # Once the tile is floating it no longer occupies a grid row.  Recompute
        # row stretch immediately so an empty trailing row collapses instead of
        # leaving dead space at the bottom of the main window.
        self._update_stretch()
        self._apply_floating_geometry(window, geometry)

        # MainWindow is not shown until after its constructor returns.  Deferring
        # the show keeps restored detached windows from flashing before it.
        QtCore.QTimer.singleShot(0, window.show)
        # Give Qt a moment to apply initial size hints before treating geometry
        # changes as user edits.
        QtCore.QTimer.singleShot(100, window.enable_geometry_notifications)

        if emit_change:
            self.layout_changed.emit()

    @QtCore.pyqtSlot(str)
    def redock_tile(self, tile_id: str) -> None:
        tile = self.tiles.get(tile_id)
        config = self.tile_configs.get(tile_id)
        window = self.floating_windows.get(tile_id)
        if tile is None or config is None or window is None:
            return

        # Preserve the user's last detached geometry so an immediate re-detach
        # in the same session uses the same useful size/location.
        config.floating_geometry = self._geometry_as_list(window.geometry())

        # Someone may have filled the former grid cells while this panel was
        # detached.  Never overlap them: find the next free position with the
        # same span.  The stored row/column are otherwise preserved.
        candidate = DashboardTileConfig(
            tile_id=config.tile_id,
            tile_type=config.tile_type,
            title=config.title,
            row=config.row,
            column=config.column,
            row_span=config.row_span,
            column_span=config.column_span,
            removable=config.removable,
            floating=False,
            visible=True,
            config=dict(config.config),
        )
        if not self._placement_available(candidate, exclude_tile_id=tile_id):
            row, column = self._first_free_position(
                row_span=max(1, config.row_span),
                column_span=max(1, config.column_span),
            )
            config.row = row
            config.column = column

        config.floating = False
        config.visible = True
        self._ensure_grid_contains(config)
        central = window.takeCentralWidget()
        if central is not None:
            central.setParent(self)
        window.force_close()
        window.deleteLater()
        self.floating_windows.pop(tile_id, None)

        tile.set_floating_state(False)
        self._add_tile_to_grid(tile, config)
        self.layout_changed.emit()


    @QtCore.pyqtSlot(str)
    def close_floating_tile(self, tile_id: str) -> None:
        """Close a floating panel without redocking or destroying its config.

        The tile is reparented back to the DashboardWidget only as an invisible
        QObject/Qt owner. It is *not* inserted into the grid. Keeping the same
        tile instance alive preserves signal connections, plot buffers and
        singleton child widgets such as the valve canvas and recording panel.
        """

        tile = self.tiles.get(tile_id)
        config = self.tile_configs.get(tile_id)
        window = self.floating_windows.get(tile_id)
        if tile is None or config is None or window is None or not config.floating:
            return

        config.floating_geometry = self._geometry_as_list(window.geometry())
        config.visible = False

        central = window.takeCentralWidget()
        if central is not None:
            central.setParent(self)
            central.hide()

        window.force_close()
        window.deleteLater()
        self.floating_windows.pop(tile_id, None)

        self._update_stretch()
        self.layout_changed.emit()

    @QtCore.pyqtSlot(str)
    def reopen_tile(self, tile_id: str) -> None:
        """Reopen a panel previously closed with its floating-window X."""

        tile = self.tiles.get(tile_id)
        config = self.tile_configs.get(tile_id)
        if tile is None or config is None or config.visible:
            return

        # A window can only be closed through this path while floating, but
        # retaining the docked branch makes hand-edited YAML robust. Validate
        # before changing visibility so a failed reopen leaves the panel closed.
        if config.floating:
            config.visible = True
            self._float_tile(tile_id, geometry=config.floating_geometry, emit_change=True)
        else:
            candidate = DashboardTileConfig(
                tile_id=config.tile_id,
                tile_type=config.tile_type,
                title=config.title,
                row=config.row,
                column=config.column,
                row_span=config.row_span,
                column_span=config.column_span,
                removable=config.removable,
                floating=False,
                visible=True,
                config=dict(config.config),
            )
            self._validate_placement(candidate, exclude_tile_id=tile_id)
            config.visible = True
            self._ensure_grid_contains(config)
            self._add_tile_to_grid(tile, config)
            self.layout_changed.emit()

    def closed_tile_ids(self) -> list[str]:
        """Return persisted panels that are currently closed/hidden."""

        return [
            tile_id
            for tile_id, config in self.tile_configs.items()
            if not config.visible
        ]


    @QtCore.pyqtSlot(str)
    def _on_floating_geometry_changed(self, tile_id: str) -> None:
        """Persist user-driven detached-window moves/resizes as layout edits."""

        config = self.tile_configs.get(tile_id)
        window = self.floating_windows.get(tile_id)
        if config is None or window is None or not config.floating:
            return
        config.floating_geometry = self._geometry_as_list(window.geometry())
        self.layout_changed.emit()

    def _floating_geometry(self, tile_id: str) -> list[int] | None:
        window = self.floating_windows.get(tile_id)
        if window is not None:
            return self._geometry_as_list(window.geometry())
        config = self.tile_configs.get(tile_id)
        return list(config.floating_geometry) if config and config.floating_geometry else None

    @staticmethod
    def _geometry_as_list(rect: QtCore.QRect) -> list[int]:
        return [rect.x(), rect.y(), rect.width(), rect.height()]

    def _apply_floating_geometry(
        self,
        window: DetachedTileWindow,
        geometry: list[int] | None,
    ) -> None:
        if geometry and len(geometry) >= 4:
            x, y, width, height = [int(v) for v in geometry[:4]]
            rect = QtCore.QRect(x, y, max(320, width), max(240, height))
            screens = QtWidgets.QApplication.screens()
            if any(screen.availableGeometry().intersects(rect) for screen in screens):
                window.setGeometry(rect)
                return

        # A portable default for first detach or a monitor arrangement that no
        # longer matches the saved desktop geometry.
        host = self.window()
        host_rect = host.geometry() if host is not None else QtCore.QRect(100, 100, 1200, 800)
        width = max(520, min(1000, int(host_rect.width() * 0.55)))
        height = max(360, min(800, int(host_rect.height() * 0.65)))
        window.resize(width, height)

        # Newly spawned floating panels should not all land exactly on top of
        # one another.  Cascade them by a small amount while keeping the offset
        # bounded so the windows remain close to the main application.
        floating_index = max(0, len(self.floating_windows) - 1)
        cascade = (floating_index % 8) * 28
        window.move(host_rect.x() + 40 + cascade, host_rect.y() + 40 + cascade)

    def close_detached_windows_for_shutdown(self) -> None:
        """Close top-level hosts without redocking them during app shutdown."""

        for tile_id, window in list(self.floating_windows.items()):
            config = self.tile_configs.get(tile_id)
            if config is not None:
                config.floating_geometry = self._geometry_as_list(window.geometry())
            window.force_close()

    def dispose_floating_windows(self) -> None:
        """Destroy detached hosts before rebuilding the entire dashboard."""

        for tile_id, window in list(self.floating_windows.items()):
            central = window.takeCentralWidget()
            if central is not None:
                central.setParent(None)
                central.deleteLater()
            window.force_close()
            window.deleteLater()
        self.floating_windows.clear()

    # ------------------------------------------------------------------
    # Dashboard configuration / edit mode
    # ------------------------------------------------------------------
    def set_dashboard_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = bool(enabled)
        for tile in self.tiles.values():
            tile.set_dashboard_edit_mode(self._edit_mode)

    def current_config(self) -> DashboardConfig:
        for tile_id, config in self.tile_configs.items():
            if config.floating and config.visible:
                config.floating_geometry = self._floating_geometry(tile_id)
        return DashboardConfig(
            rows=self.rows,
            columns=self.columns,
            row_stretches=list(self.row_stretches),
            column_stretches=list(self.column_stretches),
            tiles=[self.tile_configs[tile_id] for tile_id in self.tiles],
            dock_state=None,
            dock_layout_version="fixed_grid_v4_8col_spawn_floating",
        )

    def set_grid_size(
        self,
        rows: int,
        columns: int,
        *,
        row_stretches: Iterable[int] | None = None,
        column_stretches: Iterable[int] | None = None,
        emit_change: bool = True,
    ) -> None:
        self.rows = max(1, int(rows))
        self.columns = max(1, int(columns))
        self.row_stretches = self._normalized_stretches(
            row_stretches if row_stretches is not None else self.row_stretches,
            self.rows,
            default=1,
        )
        self.column_stretches = self._normalized_stretches(
            column_stretches if column_stretches is not None else self.column_stretches,
            self.columns,
            default=1,
        )
        self._update_stretch()
        if emit_change:
            self.layout_changed.emit()

    def _ensure_grid_contains(self, config: DashboardTileConfig) -> None:
        required_rows = max(1, config.row + max(1, config.row_span))
        required_columns = max(1, config.column + max(1, config.column_span))
        if required_rows > self.rows:
            self.rows = required_rows
            self.row_stretches.extend([1] * (self.rows - len(self.row_stretches)))
        if required_columns > self.columns:
            self.columns = required_columns
            self.column_stretches.extend([1] * (self.columns - len(self.column_stretches)))
        self._update_stretch()

    def _validate_placement(
        self,
        config: DashboardTileConfig,
        *,
        exclude_tile_id: str | None = None,
    ) -> None:
        if config.floating or not config.visible:
            return
        desired = self._occupied_cells(config)
        for tile_id, existing in self.tile_configs.items():
            if tile_id == exclude_tile_id or existing.floating or not existing.visible:
                continue
            overlap = desired.intersection(self._occupied_cells(existing))
            if overlap:
                locations = ", ".join(f"({row}, {column})" for row, column in sorted(overlap))
                raise ValueError(
                    f"Tile {config.tile_id!r} overlaps {tile_id!r} in grid cell(s) {locations}. "
                    "Choose another row/column, reduce the tile span, or detach one of the panels."
                )

    @staticmethod
    def _occupied_cells(config: DashboardTileConfig) -> set[tuple[int, int]]:
        return {
            (row, column)
            for row in range(max(0, config.row), max(0, config.row) + max(1, config.row_span))
            for column in range(
                max(0, config.column),
                max(0, config.column) + max(1, config.column_span),
            )
        }

    def _update_stretch(self) -> None:
        """Apply stretch only to rows that currently contain docked tiles.

        ``self.rows`` remains the persisted logical grid size, but an empty row
        must not consume visible height.  This is especially important after a
        bottom-row tile is detached and for panels spawned directly as floating
        windows whose preferred redock row may be beyond the current grid.
        """

        occupied_rows: set[int] = set()
        for config in self.tile_configs.values():
            if config.floating or not config.visible:
                continue
            start = max(0, int(config.row))
            span = max(1, int(config.row_span))
            occupied_rows.update(range(start, start + span))

        # Clear a generous range so stale stretch factors do not survive when
        # the grid is reduced or when the formerly-last row becomes empty.
        for row in range(max(self.rows, 32)):
            configured = self.row_stretches[row] if row < len(self.row_stretches) else 0
            stretch = configured if row in occupied_rows else 0
            self.grid.setRowStretch(row, stretch)
            self.grid.setRowMinimumHeight(row, 0)

        for column in range(max(self.columns, 32)):
            stretch = self.column_stretches[column] if column < len(self.column_stretches) else 0
            self.grid.setColumnStretch(column, stretch)

        self.grid.invalidate()
        self.updateGeometry()
