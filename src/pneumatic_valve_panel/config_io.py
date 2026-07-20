from __future__ import annotations

from pathlib import Path

import yaml

from .models import PanelConfig


def load_panel_config(path: str | Path) -> PanelConfig:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return PanelConfig.from_dict(data)


class _NoAliasSafeDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):  # noqa: D401 - PyYAML hook
        return True


def save_panel_config(panel_config: PanelConfig, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(
            panel_config.to_dict(),
            f,
            Dumper=_NoAliasSafeDumper,
            sort_keys=False,
            allow_unicode=True,
        )
