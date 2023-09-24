"""Command-line client for reading Ninebot scooter registers

Running with no arguments will start the ninebot sensor and dump all data.

It is also possible to only read specific registers using flags, see --help.
"""

import argparse
import asyncio
import logging
from typing import Any

from home_assistant_bluetooth import BluetoothServiceInfo

from ninebot_ble import (
    BmsIdx,
    CtrlIdx,
    NinebotBleSensor,
    NinebotClient,
    async_scooter_scan,
    get_register_desc,
    iter_register,
)

logger = logging.getLogger(__name__)


def dump_reg(name: str, val: Any, unit: str) -> None:
    print(f"{name:<40}: {val} {unit}")


async def main() -> None:
    logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
    logging.getLogger("bleak.backends.bluezdbus.manager").level = logging.WARNING
    logging.getLogger("bleak.backends.bluezdbus.client").level = logging.WARNING

    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter, description=__doc__)

    arg_mapping: dict[str, BmsIdx | CtrlIdx] = {}
    for idx in iter_register(CtrlIdx, BmsIdx):
        arg = "_".join(str(idx).lower().split())
        arg_mapping[arg] = idx
        parser.add_argument("--" + arg, action="store_true", help=f"read {str(idx).lower()}")

    args = parser.parse_args()

    device, advertisement = await async_scooter_scan()

    indices: list[BmsIdx | CtrlIdx] = []
    for idx_arg, idx in arg_mapping.items():
        if args.__dict__.get(idx_arg):
            indices.append(idx)

    if len(indices) > 0:
        client = NinebotClient()
        try:
            await client.connect(device)
            for idx in indices:
                val = await client.read_reg(idx)
                desc = get_register_desc(idx)
                dump_reg(str(idx), val, desc.unit or "")
        finally:
            await client.disconnect()
        return
    else:
        nb = NinebotBleSensor()
        try:
            nb.update(BluetoothServiceInfo.from_advertisement(device, advertisement, "Unknown"))
            update = await nb.async_poll(device)
            print("Title:       ", update.title)
            print("Name:        ", update.devices[None].name)
            print("Model:       ", update.devices[None].model)
            print("Manufacturer:", update.devices[None].manufacturer)
            print("SW version:  ", update.devices[None].sw_version)
            print("HW version:  ", update.devices[None].hw_version)
            print("-" * 20 + " Registers " + "-" * 20)
            for dk, dv in update.entity_values.items():
                unit = update.entity_descriptions[dk].native_unit_of_measurement
                if not unit:
                    unit_str = ""
                else:
                    unit_str = str(unit)
                print(f"{dv.name:<40}: {dv.native_value} {unit_str}")
        finally:
            await nb.disconnect()


def entrypoint() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    entrypoint()
