from datetime import datetime
from typing import Dict, List

from pydantic import BaseModel


class CityGetResponse(BaseModel):
    title: str
    label: str
    group: str
    rank: int
    type: str


class CitySuggestionsResponse(BaseModel):
    data: List[CityGetResponse]


class GetScheduleResponse(BaseModel):
    data: List[str]
    total: int
    page: int
    page_max: int
    page_size: int


class PriceInfo(BaseModel):
    value: float
    currency: str


class TripPricesResponse(BaseModel):
    __root__: Dict[str, PriceInfo]


class RowCell(BaseModel):
    primary: str
    secondary: str


class Fare(BaseModel):
    code: str
    marketing_carrier_fare_class_name: str
    price: str
    currency: str


class BookingData(BaseModel):
    departure_station_uid: str
    departure_station_title: str
    departure_station_city: str
    arrival_station_uid: str
    arrival_station_title: str
    arrival_station_city: str
    departure_time_utc: datetime
    departure_time_local: datetime
    arrival_time_utc: datetime
    arrival_time_local: datetime
    carrier_code: str
    carrier_title: str
    duration_str: str
    price: float
    currency: str
    n_segments: int
    fare_class: str
    booking_url: str


class TripInfo(BaseModel):
    id: int
    carrier: RowCell
    times: RowCell
    duration: RowCell
    stations: RowCell
    segments: RowCell
    price: RowCell
    fares: List[Fare]
    booking_data: BookingData


class TripsResponse(BaseModel):
    data: List[TripInfo]
    total: int
    page: int
    page_max: int
    page_size: int
