"""
Serialize-deserialize models
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class Carrier(BaseModel):
    code: str
    name: str
    enabled: bool
    supports_return: bool


class CarrierControls(BaseModel):
    enabled: Optional[bool] = True
    supports_return: Optional[bool] = False


class CarrierControlsResponse(BaseModel):
    success: bool
    n_cities_created: int
    n_ranks_updated: int
    n_connections_updated: int
    errors: List[str]
    updates: List[str]


class Country(BaseModel):
    code: str
    name: str


class City(BaseModel):
    code: str
    country: str
    name: Optional[str]
    translations: Dict[str, str]
    ranks: Dict[str, str]


class CarrierUpdateTaskResponse(BaseModel):
    task_code: str

    # code = fields.CharField(max_length=4, null=False)
    # task_code = fields.CharField(max_length=31, null=False, unique=True, db_index=True)
    # started = fields.DatetimeField(null=False)
    # heartbeat = fields.DatetimeField()
    # ended = fields.DatetimeField(null=True)
    # success = fields.BooleanField(null=True)
    # traceback = fields.TextField(null=True)
    # parameters = fields.JSONField(null=False)
    # result = fields.JSONField(null=True)


class TaskShort(BaseModel):
    task_code: str
    carrier_code: str
    started: datetime
    ended: Optional[datetime]
    runing: bool
    duration_minutes: int
    n_cities_created: Optional[int]
    n_ranks_updated: Optional[int]
    n_connections_updated: Optional[int]
    n_errors: Optional[int]
    success: Optional[bool]


class TaskLong(BaseModel):
    task_code: str
    carrier_code: str
    started: datetime
    ended: Optional[datetime]
    runing: bool
    duration_minutes: int
    success: Optional[bool]
    parameters: Optional[Dict[str, Any]]
    result: Optional[Dict[str, Any]]
    traceback: Optional[str]


class CountryCreateRequest(BaseModel):
    code: str
    name: str
