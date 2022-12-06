from typing import Optional

from pydantic import BaseModel, Field


class Eip1559Model(BaseModel):
    max_fee: int = Field(..., alias="maxFee")
    base_fee: int = Field(..., alias="baseFee")
    max_priority_fee: int = Field(..., alias="maxPriorityFee")

    class Config:
        allow_population_by_field_name = True
        response_by_alias = True


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
