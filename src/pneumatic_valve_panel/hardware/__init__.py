from .device_manager import DeviceManager, DeviceWorker, SerialDeviceService

# Backwards-compatible names from the single-device implementation.
HardwareService = DeviceManager
HardwareWorker = DeviceWorker

__all__ = ["DeviceManager", "DeviceWorker", "HardwareService", "HardwareWorker", "SerialDeviceService"]
