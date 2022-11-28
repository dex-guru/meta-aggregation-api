from pydantic import BaseModel


class ChainModel(BaseModel):
    name: str
    chain_id: int
    description: str
    native_token_address: str
