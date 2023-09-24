import asyncio
import logging
import time

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from .const import NINEBOT_MANUFACTURER_ID

_LOGGER = logging.getLogger(__name__)


async def async_scooter_scan() -> tuple[BLEDevice, AdvertisementData]:
    """Scans the Bluetooth network for a ninebot scooter."""
    scan_queue: asyncio.Queue[tuple[BLEDevice, AdvertisementData]] = asyncio.Queue(100)

    async def _on_scan_found(dev: BLEDevice, adv: AdvertisementData) -> None:
        _LOGGER.debug("scan found: %s | %s", dev, adv)
        await scan_queue.put((dev, adv))

    async def scan() -> tuple[BLEDevice, AdvertisementData] | None:
        async with BleakScanner(scanning_mode="active", detection_callback=_on_scan_found):
            deadline = time.time() + 30
            while time.time() < deadline:
                try:
                    dev, adv = scan_queue.get_nowait()
                    if NINEBOT_MANUFACTURER_ID in adv.manufacturer_data:
                        return dev, adv
                except asyncio.QueueEmpty:
                    await asyncio.sleep(0.1)
        return None

    result = await scan()
    if result is None:
        raise RuntimeError("Unable to find scooter")
    return result
