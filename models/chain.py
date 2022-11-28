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
    native_token: TokenModel

    def get_name_by_id(self, chain_id: int) -> str:
        for name, chain in self.__dict__.items():
            if chain.chain_id == chain_id:
                return name
        raise ValueError(f'Chain with id {chain_id} not found')

    def get_id_by_name(self, name: str) -> int:
        return self.__getattribute__(name).chain_id

