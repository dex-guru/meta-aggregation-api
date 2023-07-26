from typing import Optional

from pydantic import BaseModel, conint, constr


class TokenModel(BaseModel):
    address: constr(to_lower=True)
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
    address: constr(to_lower=True)
    name: str


class ProvidersConfigModel(BaseModel):
    limit_order: list[ProviderInfoModel]
    market_order: list[ProviderInfoModel]


class AllProvidersConfigModel(ProvidersConfigModel, BaseModel):
    chain_id: Optional[int] = None

