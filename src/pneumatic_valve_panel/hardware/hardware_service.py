"""Compatibility imports for code written against v6 HardwareService.

The application now uses :class:`DeviceManager`.  ``HardwareService`` is kept as
an alias so external imports fail gracefully during migration.
"""

from .device_manager import DeviceManager, DeviceWorker, SerialDeviceService

HardwareService = DeviceManager
HardwareWorker = DeviceWorker

__all__ = ["DeviceManager", "DeviceWorker", "HardwareService", "HardwareWorker", "SerialDeviceService"]
