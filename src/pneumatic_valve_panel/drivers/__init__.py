from __future__ import annotations

"""Device drivers, looked up by name from ``config/devices.yaml``.

Adding a new instrument
-----------------------
1. Copy ``_template.py`` in this folder to a new file, e.g. ``my_gauge.py``.
2. Rename the class, change the name in ``@register_driver("my_gauge")`` and
   fill in the marked methods.
3. Add a block to ``config/devices.yaml``::

       my_gauge:
         enabled: true
         driver: my_gauge
         connection:
           port: COM7
           baudrate: 9600

4. Add the gauge's channels to ``config/sensors.yaml``.

Every ``.py`` file in this folder whose name does not start with ``_`` is
imported automatically at start-up, so there is no list to keep up to date.
Run ``python run_app.py --list-drivers`` to see what was found.
"""

import importlib
import logging
import pkgutil
from typing import Any, Callable, TypeVar

_log = logging.getLogger(__name__)

T = TypeVar("T")

_DRIVERS: dict[str, Callable[..., Any]] = {}
_DESCRIPTIONS: dict[str, str] = {}
_LOAD_ERRORS: dict[str, str] = {}
_loaded = False


def register_driver(name: str, *, description: str = "") -> Callable[[T], T]:
    """Class decorator that makes a driver available under ``name``."""

    def decorator(factory: T) -> T:
        key = str(name).strip()
        if not key:
            raise ValueError("Driver name must not be empty")
        existing = _DRIVERS.get(key)
        if existing is not None and existing is not factory:
            raise ValueError(f"Two drivers are both registered as {key!r}")
        _DRIVERS[key] = factory  # type: ignore[assignment]
        doc = (getattr(factory, "__doc__", "") or "").strip().splitlines()
        _DESCRIPTIONS[key] = description or (doc[0] if doc else "")
        return factory

    return decorator


def load_drivers() -> None:
    """Import every driver module in this package once.

    A module that fails to import is recorded (see :func:`driver_load_errors`)
    instead of stopping the application, so one broken add-in cannot prevent
    the relay controller from starting.
    """

    global _loaded
    if _loaded:
        return
    _loaded = True
    for module in pkgutil.iter_modules(__path__):
        if module.name.startswith("_"):
            continue
        qualified = f"{__name__}.{module.name}"
        try:
            importlib.import_module(qualified)
        except Exception as exc:  # pragma: no cover - depends on add-in code
            _LOAD_ERRORS[module.name] = f"{type(exc).__name__}: {exc}"
            _log.exception("Could not load driver module %s", qualified)


def available_drivers() -> dict[str, str]:
    """Return ``{driver name: one-line description}``."""

    load_drivers()
    return dict(sorted(_DESCRIPTIONS.items()))


def driver_load_errors() -> dict[str, str]:
    load_drivers()
    return dict(_LOAD_ERRORS)


def create_driver(name: str, options: dict[str, Any] | None = None) -> Any:
    """Construct the driver registered as ``name`` with ``options`` kwargs."""

    load_drivers()
    try:
        factory = _DRIVERS[name]
    except KeyError:
        known = ", ".join(sorted(_DRIVERS)) or "none"
        hint = ""
        if _LOAD_ERRORS:
            hint = " Some driver files failed to load: " + "; ".join(
                f"{module}: {error}" for module, error in _LOAD_ERRORS.items()
            )
        raise KeyError(f"Unknown driver {name!r}. Available drivers: {known}.{hint}") from None
    try:
        return factory(**dict(options or {}))
    except TypeError as exc:
        raise TypeError(f"Driver {name!r} rejected its options {options!r}: {exc}") from exc


__all__ = [
    "available_drivers",
    "create_driver",
    "driver_load_errors",
    "load_drivers",
    "register_driver",
]
