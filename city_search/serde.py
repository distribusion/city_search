from typing import Dict, Optional

from pydantic import BaseModel


class Carrier(BaseModel):
    code: str
    name: str


class Country(BaseModel):
    name: str


class City(BaseModel):
    code: str
    country: str
    name: Optional[str]
    translations: Dict[str, str]
    ranks: Dict[str, str]
