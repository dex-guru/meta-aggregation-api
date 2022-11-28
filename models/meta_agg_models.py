from typing import List, Optional

from pydantic import BaseModel, Field

from models.provider_response_models import SwapSources


class MetaSwapPriceResponse(BaseModel):
    sources: List[SwapSources]
    buy_amount: str = Field(alias='buyAmount')
    gas: str
    sell_amount: str = Field(alias='sellAmount')
    gas_price: str = Field(alias='gasPrice')
    value: str
    price: str

    class Config:
        allow_population_by_field_name = False
        response_by_alias = False


class MetaPriceModel(BaseModel):
    provider: str
    quote: MetaSwapPriceResponse
    is_allowed: bool
    is_best: Optional[bool] = None  # none for request with one provider
    approve_cost: int = 0


class SwapQuoteResponse(BaseModel):
    sources: list
    buy_amount: str = Field(alias='buyAmount')
    gas: str
    sell_amount: str = Field(alias='sellAmount')
    to: str
    data: str
    gas_price: str = Field(alias='gasPrice')
    value: str
    price: str

    class Config:
        allow_population_by_field_name = False
        response_by_alias = False
