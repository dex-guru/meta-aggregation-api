from pydantic import BaseModel


class TokenModel(BaseModel):
    address: str
    name: str
    symbol: str
    decimals: int


class ChainModel(BaseModel):
    name: str
    chain_id: int
    description: str
    native_token: TokenModel = None
    eip1559: bool


class ProviderInfoModel(BaseModel):
    display_name: str
    address: str
    name: str


class ProvidersConfigModel(BaseModel):
    limit_order: list[ProviderInfoModel]
    market_order: list[ProviderInfoModel]
