"""
Serialize-deserialize models
"""
from typing import Dict, List, Optional

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
    name: str


class City(BaseModel):
    code: str
    country: str
    name: Optional[str]
    translations: Dict[str, str]
    ranks: Dict[str, str]
