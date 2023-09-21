import datetime

from sensor_state_data.enum import StrEnum


class SerialParser:
    class ProductSeries(StrEnum):
        E = "N2G"
        MAX = "N4G"
        F = "N5G"

    PRODUCT_VERSION_MAPPING = {
        ProductSeries.E: {
            "D": "E22",
            "G": "E22E",
            "I": "E22D",
            "V": "E25",
            "Y": "E25D",
            "X": "E25E",
            "Z": "E25A",
            "R": "E45D",
            "O": "E45E",
            "M": "E45E",
            "Q": "E45 (30 km/h)",
        },
        ProductSeries.MAX: {
            "S": "G30P (30 km/h)",
            "C": "G30 (25 km/h)",
            "E": "G30D blue (20 km/h)",
            "P": "G30E (25 km/h)",
            "N": "G30LP (30 km/h)",
            "A": "G30LE (25 km/h)",
            "O": "G30LE (25 km/h)",
            "M": "G30LD (20 km/h)",
            "T": "G30M (25 km/h)",
            "2": "SNSC2.2A (25 km/h)",
            "0": "SNSC2.3 (25 km/h)",
            "1": "Audi EKS G30D (20 km/h)",
        },
        ProductSeries.F: {
            "A": "F20",
            "B": "F20D",
            "C": "F30",
            "D": "F30D",
            "E": "F40",
            "F": "F40E",
            "G": "F40D",
            "H": "F60",
            "I": "F60D/F60E",
            "J": "F60D/F60E",
            "M": "F60A/F60 Asia",
            "N": "F25",
            "O": "F20A",
            "Q": "F30E",
            "R": "F40A",
            "S": "F20E/F20D (?)",
            "V": "F40",
            "W": "F25E ",
        },
    }

    def __init__(self, serial: str) -> None:
        if len(serial) < 14:
            raise ValueError(f"Unsupported serial number {serial}")
        self.product_series = self.ProductSeries(serial[:3])
        self._product_version = self.PRODUCT_VERSION_MAPPING.get(self.product_series, {}).get(serial[3], None)
        self._production_line = serial[4]
        self._year = 2000 + int(serial[5:7])
        self._week = int(serial[7:9])
        self.product_revision = serial[10]
        self.weekly_serial = int(serial[10:14])

    @property
    def production_date(self) -> datetime.datetime:
        return datetime.datetime.fromisocalendar(self._year, self._week, 1)

    @property
    def product_version(self) -> str:
        if self._product_version is None:
            return str(self.product_series) + "-series"
        return self._product_version

    def __str__(self) -> str:
        return f"Ninebot {self.product_version}"
