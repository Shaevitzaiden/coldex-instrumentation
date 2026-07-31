from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ...data.models import DashboardTileConfig
from .tile_base import TileWidget

TileFactory = Callable[[DashboardTileConfig, Any], TileWidget]


class TileRegistry:
    """Maps config type names to independent tile factories."""

    def __init__(self) -> None:
        self._factories: dict[str, TileFactory] = {}

    def register(self, tile_type: str, factory: TileFactory) -> None:
        self._factories[str(tile_type)] = factory

    def create(self, config: DashboardTileConfig, context: Any) -> TileWidget:
        try:
            factory = self._factories[config.tile_type]
        except KeyError as exc:
            raise ValueError(f"Unknown tile type: {config.tile_type}") from exc
        return factory(config, context)

    def registered_types(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))
