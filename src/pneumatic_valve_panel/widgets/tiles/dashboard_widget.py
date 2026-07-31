from __future__ import annotations

from collections.abc import Iterable

from PyQt5 import QtCore, QtWidgets

from ...data.models import DashboardConfig, DashboardTileConfig
from .tile_base import TileWidget


class DashboardWidget(QtWidgets.QWidget):
    """Stable grid-backed dashboard with an explicit layout-editing mode.

    Runtime mode is intentionally non-interactive: the tile geometry is fixed
    and only the child widgets respond to the user. Dashboard edit mode reveals
    each tile's configure/remove controls. Geometry is changed through the tile
    configuration dialog rather than Qt's native dock engine, avoiding hidden,
    overlapping, or collapsed dock panes.
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

    def add_tile(self, tile: TileWidget, config: DashboardTileConfig, *, emit_change: bool = True) -> None:
        if config.tile_id in self.tiles:
            raise ValueError(f"A dashboard tile named {config.tile_id!r} already exists")
        self._ensure_grid_contains(config)
        self._validate_placement(config)

        self.tiles[config.tile_id] = tile
        self.tile_configs[config.tile_id] = config
        tile.set_title(config.title)
        tile.set_dashboard_edit_mode(self._edit_mode)
        tile.close_requested.connect(self.remove_tile)
        tile.configure_requested.connect(self.tile_configure_requested.emit)
        self.grid.addWidget(
            tile,
            max(0, config.row),
            max(0, config.column),
            max(1, config.row_span),
            max(1, config.column_span),
        )
        if emit_change:
            self.layout_changed.emit()

    @QtCore.pyqtSlot(str)
    def remove_tile(self, tile_id: str, *, emit_change: bool = True) -> None:
        tile = self.tiles.get(tile_id)
        config = self.tile_configs.get(tile_id)
        if tile is None or config is None or not config.removable:
            return
        self.tiles.pop(tile_id, None)
        self.tile_configs.pop(tile_id, None)
        self.grid.removeWidget(tile)
        tile.deleteLater()
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
        self._ensure_grid_contains(replacement_config)
        self._validate_placement(replacement_config, exclude_tile_id=tile_id)

        self.grid.removeWidget(old_tile)
        self.tiles[tile_id] = replacement_tile
        self.tile_configs[tile_id] = replacement_config
        replacement_tile.set_title(replacement_config.title)
        replacement_tile.set_dashboard_edit_mode(self._edit_mode)
        replacement_tile.close_requested.connect(self.remove_tile)
        replacement_tile.configure_requested.connect(self.tile_configure_requested.emit)
        self.grid.addWidget(
            replacement_tile,
            max(0, replacement_config.row),
            max(0, replacement_config.column),
            max(1, replacement_config.row_span),
            max(1, replacement_config.column_span),
        )
        old_tile.deleteLater()
        self.layout_changed.emit()

    def update_tile_config(self, tile_id: str, replacement: DashboardTileConfig) -> None:
        tile = self.tiles[tile_id]
        old = self.tile_configs[tile_id]
        replacement.tile_id = tile_id
        replacement.tile_type = old.tile_type
        replacement.removable = old.removable
        self._ensure_grid_contains(replacement)
        self._validate_placement(replacement, exclude_tile_id=tile_id)

        self.tile_configs[tile_id] = replacement
        tile.set_title(replacement.title)
        self.grid.removeWidget(tile)
        self.grid.addWidget(
            tile,
            max(0, replacement.row),
            max(0, replacement.column),
            max(1, replacement.row_span),
            max(1, replacement.column_span),
        )
        self.layout_changed.emit()

    def set_dashboard_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = bool(enabled)
        for tile in self.tiles.values():
            tile.set_dashboard_edit_mode(self._edit_mode)

    def current_config(self) -> DashboardConfig:
        return DashboardConfig(
            rows=self.rows,
            columns=self.columns,
            row_stretches=list(self.row_stretches),
            column_stretches=list(self.column_stretches),
            tiles=[self.tile_configs[tile_id] for tile_id in self.tiles],
            dock_state=None,
            dock_layout_version="fixed_grid_v1",
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
        desired = self._occupied_cells(config)
        for tile_id, existing in self.tile_configs.items():
            if tile_id == exclude_tile_id:
                continue
            overlap = desired.intersection(self._occupied_cells(existing))
            if overlap:
                locations = ", ".join(f"({row}, {column})" for row, column in sorted(overlap))
                raise ValueError(
                    f"Tile {config.tile_id!r} overlaps {tile_id!r} in grid cell(s) {locations}. "
                    "Choose another row/column or reduce the tile span."
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
        # Clear a generous range so stale stretch factors do not survive when
        # the grid is reduced after loading a different configuration.
        for row in range(max(self.rows, 32)):
            stretch = self.row_stretches[row] if row < len(self.row_stretches) else 0
            self.grid.setRowStretch(row, stretch)
        for column in range(max(self.columns, 32)):
            stretch = self.column_stretches[column] if column < len(self.column_stretches) else 0
            self.grid.setColumnStretch(column, stretch)
