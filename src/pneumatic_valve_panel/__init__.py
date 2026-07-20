"""Scalable pneumatic valve panel editor/control GUI."""


def run_app(*args, **kwargs):
    """Lazy wrapper so non-GUI modules can be imported without importing PyQt5."""
    from .app import run_app as _run_app

    return _run_app(*args, **kwargs)


__all__ = ["run_app"]
