from __future__ import annotations

from sensor_state_data import (
    BinarySensorDeviceClass,
    BinarySensorValue,
    DeviceKey,
    SensorDescription,
    SensorDeviceClass,
    SensorDeviceInfo,
    SensorUpdate,
    SensorValue,
    Units,
)

from .register import BmsIdx, CtrlIdx, get_register_desc, iter_register
from .sensor import NinebotBleSensor
from .transport import NinebotClient

__version__ = "0.0.1"

__all__ = [
    "NinebotBleSensor",
    "NinebotClient",
    "BmsIdx",
    "CtrlIdx",
    "iter_register",
    "get_register_desc",
    "BinarySensorDeviceClass",
    "BinarySensorValue",
    "SensorDescription",
    "SensorDeviceInfo",
    "DeviceKey",
    "SensorUpdate",
    "SensorDeviceClass",
    "SensorDeviceInfo",
    "SensorValue",
    "Units",
]
