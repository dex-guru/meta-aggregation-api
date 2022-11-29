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
