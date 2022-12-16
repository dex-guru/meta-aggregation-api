from typing import Optional

from pydantic import BaseModel


class Eip1559Model(BaseModel):
    max_fee: int
    base_fee: int
    max_priority_fee: int


class GasPriceEip1559Model(BaseModel):
    fast: Eip1559Model
    instant: Eip1559Model
    overkill: Eip1559Model


class LegacyGasPriceModel(BaseModel):
    fast: int
    instant: int
    overkill: int


class GasResponse(BaseModel):
    source: str
    timestamp: int
    eip1559: Optional[GasPriceEip1559Model] = None
    legacy: LegacyGasPriceModel = None
