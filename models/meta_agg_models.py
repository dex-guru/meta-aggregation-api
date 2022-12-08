from typing import List, Optional

from pydantic import BaseModel, Field

from models.provider_response_models import SwapSources


class ProviderPriceResponse(BaseModel):
    provider: str
    sources: List[SwapSources]
    buy_amount: str
    gas: str
    sell_amount: str
    gas_price: str
    value: str
    price: str


class MetaPriceModel(BaseModel):
    provider: str
    price_response: ProviderPriceResponse
    is_allowed: bool
    is_best: Optional[bool] = None  # none for request with one provider
    approve_cost: int = 0


class SwapQuoteResponse(BaseModel):
    sources: list
    buy_amount: str
    gas: str
    sell_amount: str
    to: str
    data: str
    gas_price: str
    value: str
    price: str
