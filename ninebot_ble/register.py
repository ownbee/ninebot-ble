import enum
from binascii import hexlify
from struct import unpack
from typing import Any, Callable, Generator, Generic, TypeVar

from sensor_state_data import SensorDeviceClass, Units
from sensor_state_data.enum import StrEnum


class CtrlIdx(StrEnum):
    """Controller register indieces"""

    NB_INF_SN = "Scooter serial number"
    NB_INF_BTPASSWORD = "Bluetooth pairing code"
    NB_FW_VER = "Controller firmware"
    NB_INF_ERROR = "Error code"
    NB_INF_ALERM = "Alarm code"
    # NB_INF_BOOL = "Boolean state word"
    NB_INF_BOOL_LIMITSPEED = "Speed limited"
    NB_INF_BOOL_LOCK = "Scooter locked"
    NB_INF_BOOL_BEEP = "Buzzer alarm activated"
    NB_INF_BOOL_BAT2_IN = "External battery inserted"
    NB_INF_BOOL_ACT = "Scooter activated"
    # NB_INF_BTC_1 = "Volume of storage battery 1"
    # NB_INF_BTC_2 = "Volume of storage battery 2"
    # NB_INF_BTC = "Battery percentage of the scooter"
    NB_INF_ACTUAL_MIL = "Actual remaining mileage"
    NB_INF_PRD_RID_MIL = "Predicted remaining mileage"
    # NB_INF_WORKMODE = "Current operaton mode"
    NB_INF_RID_MIL = "Total mileage"
    NB_INF_RUN_TIM = "Total operation time"
    NB_INF_RID_TIM = "Total riding time"
    NB_INF_BODY_TEMP = "Scooter temperature"
    # NB_INF_BAT1_TEMP = "Battery 1 temperature"
    # NB_INF_BAT2_TEMP = "Battery 2 temperature"
    NB_INF_DRV_VOLT = "Controller supply voltage"
    NB_INF_AVRSPEED = "Average speed"
    NB_INF_VER_BMS2 = "External BMS firmware version"
    # NB_INF_VER_BMS = "Battery firmware version"
    NB_INF_VER_BLE = "BLE firmware version"
    NB_CTL_LIMIT_SPD = "Speed limit or speed limit release"
    NB_CTL_NOMALSPEED = "Speed limit value in normal mode"
    NB_CTL_LITSPEED = "Speed limit value in speed limit mode"
    NB_CTL_WORKMODE = "Operating mode"
    NB_CTL_KERS = "KERS level"
    NB_CTL_CRUISE = "Cruise control enabled"
    NB_CTL_TAIL_LIGHT = "Tail light on"
    NB_SINGLE_MIL = "Single mileage"
    NB_SINGLE_RUN_TIM = "Single operation time"
    NB_POWER = "Scooter power"


class BmsIdx(StrEnum):
    """BMS register indieces"""

    BAT_SN = "BMS serial number"
    BAT_SW_VER = "BMS firmware version"
    BAT_CAPACITY = "Battery factory capacity"
    # BAT_TOTAL_CAPACITY = "Actual capacity"
    # BAT_DESIGN_VOLTAGE = "Design voltage of the battery"
    # BAT_CYCLE_TIMES = "Cycle times of the battery"
    # BAT_CHARGE_TIMES = "Battery charging times"
    # BAT_CHARGE_CAP = "Accumulatve charge capacity of the battery"
    BAT_OVERFLOW_TIMES = "Battery overflowing times"
    BAT_OVERDISCHARGE_TIMES = "Battery over-discharging times"
    BAT_REMAINING_CAP = "Remaining battery capacity, mAh"
    BAT_REMAINING_CAP_PERCENT = "Remaining battery capacity"
    BAT_CURRENT_CUR = "Battery current"
    BAT_VOLTAGE_CUR = "Battery voltage"
    BAT_TEMP_CUR1 = "Battery temperature 1"
    BAT_TEMP_CUR2 = "Battery temperature 2"
    BAT_BALANCE_STATU = "Battery balancing open status"
    BAT_ODIS_STATE = "Battery cell undervoltage conditon"
    BAT_OCHG_STATE = "Battery cell overvoltage conditon"
    # BAT_CAP_COULO = "Battery coulombmeter capacity"
    # BAT_CAP_VOL = "Battery voltmeter capacity"
    BAT_HEALTHY = "Battery health"


class OperationMode(enum.Enum):
    NORMAL = 0
    ECO = 1
    SPORT = 2


class ChargeStatus(enum.Enum):
    CHARGING = 0
    DISCHARGING = 1
    CONNECTED_DISCHARGING = 2
    CONNECTED = 3
    IDLE = 4


class KersLevel(enum.Enum):
    OFF = 0
    MEDIUM = 1
    STRONG = 2


T = TypeVar("T")


class RegDesc(Generic[T]):
    """Register entry description."""

    def __init__(
        self,
        index_start: int,
        index_len: int,
        read_len: int,
        unpacker: Callable[[list[int]], T],
        device_class: SensorDeviceClass | None = None,
        scaler: Callable[[T], T] | None = None,
        unit: Units | None = None,
    ) -> None:
        self.index_start = index_start
        self.index_len = index_len
        self.read_len = read_len
        self.unpacker = unpacker
        self.device_class = device_class
        self.scaler = scaler
        self.unit = unit


def get_register_desc(index: CtrlIdx | BmsIdx) -> RegDesc:
    """Get register description."""
    if isinstance(index, CtrlIdx):
        return _CTRL_TABLE[index]
    return _BATT_TABLE[index]


def iter_register(*register: type[BmsIdx] | type[CtrlIdx]) -> Generator[BmsIdx | CtrlIdx, None, None]:
    for reg in register:
        for idx in reg:
            yield idx


def _unpack_string(data: list[int]) -> str:
    return bytes(data).decode()


def _unpack_hex(data: list[int]) -> str:
    return hexlify(bytes(data)).upper().decode()


def _unpack_LE16(data: list[int]) -> int:
    assert len(data) == 2
    return (data[1] << 8) | data[0]


def _unpack_LES16(data: list[int]) -> int:
    assert len(data) == 2
    return int(unpack("<h", bytes(data))[0])


def _unpack_LE16_bitfield_bool(data: list[int], pos: int) -> bool:
    word = _unpack_LE16(data)
    return (word & (1 << pos)) > 0


def _unpack_op_mode(data: list[int]) -> OperationMode:
    return OperationMode(_unpack_LE16(data))


def _unpack_U32_from2LE16(data: list[int]) -> int:
    assert len(data) == 4
    low = data[:2]
    high = data[2:]
    return _unpack_LE16(low) + (_unpack_LE16(high) << 16)


def _unpack_version(data: list[int]) -> str:
    val = _unpack_LE16(data)
    return f"{val >> 8}.{(val >> 4) & 0x0F}.{(val) & 0x0F}"


def _unpack_kers_level(data: list[int]) -> KersLevel:
    return KersLevel(_unpack_LE16(data))


_CTRL_TABLE: dict[CtrlIdx, RegDesc[Any]] = {
    CtrlIdx.NB_INF_SN: RegDesc(0x10, 7, 2, _unpack_string),
    CtrlIdx.NB_INF_BTPASSWORD: RegDesc(0x17, 3, 2, _unpack_string),
    CtrlIdx.NB_FW_VER: RegDesc(0x1A, 1, 2, _unpack_version),
    CtrlIdx.NB_INF_ERROR: RegDesc(0x1B, 1, 2, _unpack_LE16),
    CtrlIdx.NB_INF_ALERM: RegDesc(0x1C, 1, 2, _unpack_LE16),
    CtrlIdx.NB_INF_BOOL_LIMITSPEED: RegDesc(0x1D, 1, 2, lambda data: _unpack_LE16_bitfield_bool(data, 0)),
    CtrlIdx.NB_INF_BOOL_LOCK: RegDesc(0x1D, 1, 2, lambda data: _unpack_LE16_bitfield_bool(data, 1)),
    CtrlIdx.NB_INF_BOOL_BEEP: RegDesc(0x1D, 1, 2, lambda data: _unpack_LE16_bitfield_bool(data, 2)),
    CtrlIdx.NB_INF_BOOL_BAT2_IN: RegDesc(0x1D, 1, 2, lambda data: _unpack_LE16_bitfield_bool(data, 9)),
    CtrlIdx.NB_INF_BOOL_ACT: RegDesc(0x1D, 1, 2, lambda data: _unpack_LE16_bitfield_bool(data, 11)),
    CtrlIdx.NB_INF_ACTUAL_MIL: RegDesc(
        0x24,
        1,
        2,
        _unpack_LE16,
        scaler=lambda x: x / 100,
        device_class=SensorDeviceClass.DISTANCE,
        unit=Units.LENGTH_KILOMETERS,
    ),
    CtrlIdx.NB_INF_PRD_RID_MIL: RegDesc(
        0x25,
        1,
        2,
        _unpack_LE16,
        scaler=lambda x: x / 100,
        device_class=SensorDeviceClass.DISTANCE,
        unit=Units.LENGTH_KILOMETERS,
    ),
    CtrlIdx.NB_INF_RID_MIL: RegDesc(
        0x29,
        2,
        2,
        _unpack_U32_from2LE16,
        scaler=lambda x: round(x / 1000, 1),
        device_class=SensorDeviceClass.DISTANCE,
        unit=Units.LENGTH_KILOMETERS,
    ),
    CtrlIdx.NB_INF_RUN_TIM: RegDesc(
        0x32,
        2,
        2,
        _unpack_U32_from2LE16,
        scaler=lambda x: round(x / 1000, 1),
        device_class=SensorDeviceClass.DURATION,
        unit=Units.TIME_HOURS,
    ),
    CtrlIdx.NB_INF_RID_TIM: RegDesc(
        0x34,
        2,
        2,
        _unpack_U32_from2LE16,
        scaler=lambda x: round(x / 3600, 1),
        device_class=SensorDeviceClass.DURATION,
        unit=Units.TIME_HOURS,
    ),
    CtrlIdx.NB_INF_BODY_TEMP: RegDesc(
        0x3E,
        1,
        2,
        _unpack_LE16,
        scaler=lambda x: x / 10,
        device_class=SensorDeviceClass.TEMPERATURE,
        unit=Units.TEMP_CELSIUS,
    ),
    CtrlIdx.NB_INF_DRV_VOLT: RegDesc(
        0x47,
        1,
        2,
        _unpack_LE16,
        scaler=lambda x: x / 100,
        device_class=SensorDeviceClass.VOLTAGE,
        unit=Units.ELECTRIC_POTENTIAL_VOLT,
    ),
    CtrlIdx.NB_INF_AVRSPEED: RegDesc(
        0x65, 1, 2, _unpack_LE16, scaler=lambda x: x / 10, unit=Units.SPEED_KILOMETERS_PER_HOUR
    ),
    CtrlIdx.NB_INF_VER_BMS2: RegDesc(0x66, 1, 2, _unpack_LE16),
    CtrlIdx.NB_INF_VER_BLE: RegDesc(0x68, 1, 2, _unpack_version),
    CtrlIdx.NB_CTL_LIMIT_SPD: RegDesc(
        0x72, 1, 2, _unpack_LES16, scaler=lambda x: x / 10, unit=Units.SPEED_KILOMETERS_PER_HOUR
    ),
    CtrlIdx.NB_CTL_NOMALSPEED: RegDesc(
        0x73, 1, 2, _unpack_LES16, scaler=lambda x: x / 10, unit=Units.SPEED_KILOMETERS_PER_HOUR
    ),
    CtrlIdx.NB_CTL_LITSPEED: RegDesc(
        0x74, 1, 2, _unpack_LES16, scaler=lambda x: x / 10, unit=Units.SPEED_KILOMETERS_PER_HOUR
    ),
    CtrlIdx.NB_CTL_WORKMODE: RegDesc(0x75, 1, 2, _unpack_op_mode),
    CtrlIdx.NB_CTL_KERS: RegDesc(0x7B, 1, 2, _unpack_kers_level),
    CtrlIdx.NB_CTL_CRUISE: RegDesc(0x7C, 1, 2, _unpack_LE16),
    CtrlIdx.NB_CTL_TAIL_LIGHT: RegDesc(0x7D, 1, 2, _unpack_LE16),
    CtrlIdx.NB_SINGLE_MIL: RegDesc(
        0xB9,
        1,
        2,
        _unpack_LE16,
        scaler=lambda x: x / 100,
        device_class=SensorDeviceClass.DISTANCE,
        unit=Units.LENGTH_KILOMETERS,
    ),
    CtrlIdx.NB_SINGLE_RUN_TIM: RegDesc(
        0xBA,
        1,
        2,
        _unpack_LE16,
        scaler=lambda x: round(x / 3600, 1),
        device_class=SensorDeviceClass.DURATION,
        unit=Units.TIME_HOURS,
    ),
    CtrlIdx.NB_POWER: RegDesc(
        0xBA,
        1,
        2,
        _unpack_LE16,
        unit=Units.POWER_WATT,
    ),
}

_BATT_TABLE: dict[BmsIdx, RegDesc[Any]] = {
    BmsIdx.BAT_SN: RegDesc(0x10, 7, 2, _unpack_hex),
    BmsIdx.BAT_SW_VER: RegDesc(0x17, 1, 2, _unpack_LE16),
    BmsIdx.BAT_CAPACITY: RegDesc(0x18, 1, 2, _unpack_LE16),
    BmsIdx.BAT_OVERFLOW_TIMES: RegDesc(0x1F, 1, 2, _unpack_LE16, scaler=lambda x: x & 0xFF),
    BmsIdx.BAT_OVERDISCHARGE_TIMES: RegDesc(0x1F, 1, 2, _unpack_LE16, scaler=lambda x: (x >> 8) & 0xFF),
    BmsIdx.BAT_REMAINING_CAP: RegDesc(0x31, 1, 2, _unpack_LE16),
    BmsIdx.BAT_REMAINING_CAP_PERCENT: RegDesc(
        0x32, 1, 2, _unpack_LE16, device_class=SensorDeviceClass.BATTERY, unit=Units.PERCENTAGE
    ),
    BmsIdx.BAT_CURRENT_CUR: RegDesc(
        0x33, 1, 2, _unpack_LES16, scaler=lambda x: x / 100, unit=Units.ELECTRIC_CURRENT_AMPERE
    ),
    BmsIdx.BAT_VOLTAGE_CUR: RegDesc(
        0x34, 1, 2, _unpack_LE16, scaler=lambda x: x / 100, unit=Units.ELECTRIC_POTENTIAL_VOLT
    ),
    BmsIdx.BAT_TEMP_CUR1: RegDesc(0x35, 1, 2, _unpack_LE16, scaler=lambda x: (x & 0xFF) - 20, unit=Units.TEMP_CELSIUS),
    BmsIdx.BAT_TEMP_CUR2: RegDesc(
        0x35, 1, 2, _unpack_LE16, scaler=lambda x: ((x >> 8) & 0xFF) - 20, unit=Units.TEMP_CELSIUS
    ),
    BmsIdx.BAT_BALANCE_STATU: RegDesc(0x36, 1, 2, _unpack_LE16),
    BmsIdx.BAT_ODIS_STATE: RegDesc(0x37, 1, 2, _unpack_LE16),
    BmsIdx.BAT_OCHG_STATE: RegDesc(0x38, 1, 2, _unpack_LE16),
    BmsIdx.BAT_HEALTHY: RegDesc(0x3B, 1, 2, _unpack_LE16, unit=Units.PERCENTAGE),
}
