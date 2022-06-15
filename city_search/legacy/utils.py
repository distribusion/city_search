from collections import namedtuple
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

import pytz
from fastapi import HTTPException

Item = namedtuple(
    "Item", ["title", "label", "group", "rank", "type", "translations", "timezone"]
)

CityCode = str
StationCode = str


@dataclass
class ItemsIndex:
    keys: List[CityCode]
    ngrams: Dict[str, Set[int]]


@dataclass
class StationInfo:
    name: str
    timezone: str


@dataclass
class CarrierInfo:
    name: str
    supports_return_trips: bool
    enabled: bool


@dataclass
class Globals:
    __slots__ = (
        "city_dict",
        "cities_index_wr",
        "cities_top_wr",
        "city_connections_wr",
        "cities_index_nr",
        "cities_top_nr",
        "city_connections_nr",
        "city_stations",
        "station_info",
        "carrier_info",
    )

    city_dict: Optional[Dict[CityCode, Item]]
    cities_index_wr: Optional[ItemsIndex]
    cities_top_wr: Optional[List[CityCode]]
    city_connections_wr: Optional[Dict[str, Any]]
    cities_index_nr: Optional[ItemsIndex]
    cities_top_nr: Optional[List[CityCode]]
    city_connections_nr: Optional[Dict[CityCode, Any]]
    city_stations: Optional[Dict[CityCode, List[StationCode]]]
    station_info: Optional[Dict[StationCode, StationInfo]]
    carrier_info: Optional[Dict[str, CarrierInfo]]


class GlobalsAccess:
    def __init__(self, global_vars: Globals):
        if (
            global_vars.city_stations is None
            or global_vars.station_info is None
            or global_vars.carrier_info is None
            or global_vars.city_dict is None
        ):
            raise HTTPException(503, "Cache not initialized")

        self.carrier_info = global_vars.carrier_info
        self.city_stations = global_vars.city_stations
        self.station_info: Dict[StationCode, StationInfo] = global_vars.station_info
        self.city_dict: Dict[CityCode, Item] = global_vars.city_dict

    def get_station_timezone_by_code(self, code: str) -> Optional[pytz.BaseTzInfo]:
        try:
            return pytz.timezone(self.station_info[code].timezone)
        except KeyError:
            return None

    def get_station_title_by_code(self, code: str) -> Optional[str]:
        try:
            return self.station_info[code].name
        except KeyError:
            return None

    def get_carrier_title_by_code(self, code: str) -> Optional[str]:
        try:
            return self.carrier_info[code].name
        except KeyError:
            return None

    def get_city_title_by_code(self, code: str) -> Optional[str]:
        try:
            return self.city_dict[code].title
        except KeyError:
            return None

    def get_city_stations_by_code(self, code: str) -> Optional[List[StationCode]]:
        try:
            return self.city_stations[code]
        except KeyError:
            return None

    def get_city_timezone_by_code(self, code: str) -> Optional[pytz.BaseTzInfo]:
        try:
            return pytz.timezone(self.city_dict[code].timezone)
        except KeyError:
            return None

    def get_all_enabled_carriers(self, with_return: bool) -> List[str]:
        rv = list()
        for carrier_code, carrier_info in self.carrier_info.items():
            if (
                not with_return or carrier_info.supports_return_trips
            ) and carrier_info.enabled:
                rv.append(carrier_code)
        return rv
