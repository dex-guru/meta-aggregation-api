from typing import Optional

from pydantic import BaseModel, constr, conint


class TokenModel(BaseModel):
    address: constr(min_length=42, max_length=42, to_lower=True)
    name: str
    symbol: str
    decimals: conint(gt=0)


class ChainModel(BaseModel):
    name: str
    chain_id: int
    description: str
    native_token: TokenModel = None
    eip1559: bool


class ProviderInfoModel(BaseModel):
    display_name: str
    address: constr(min_length=42, max_length=42, to_lower=True)
    name: str


class ProvidersConfigModel(BaseModel):
    limit_order: list[ProviderInfoModel]
    market_order: list[ProviderInfoModel]


class AllProvidersConfigModel(ProvidersConfigModel, BaseModel):
    chain_id: Optional[int] = None
