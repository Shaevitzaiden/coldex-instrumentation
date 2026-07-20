from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import PanelConfig


def load_panel_config(path: str | Path) -> PanelConfig:
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle) or {}
    return PanelConfig.from_dict(data)


def save_panel_config(config: PanelConfig, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config.to_dict(), handle, sort_keys=False)
