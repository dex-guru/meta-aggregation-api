from abc import ABC, abstractmethod
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


class ChainSwapInfo(ABC):

    def __init__(self, chain_id: int):
        self._chain_id = chain_id

    @abstractmethod
    async def get_type(self) -> str:
        """
        Args:
            self: Access the class attributes

        Returns:
            A cross_chain or single_chain
        """

    @property
    def chain_id(self):
        return self._chain_id


class SingleChainSwapInfo(ChainSwapInfo):

    def __init__(self, chain_id: int):
        super().__init__(chain_id)

    def get_type(self) -> str:
        return 'single_chain'


class CrossChainSwapInfo(ChainSwapInfo):
    def __init__(self, give_chain_id: int, take_chain_id: int):
        super().__init__(give_chain_id)
        self._give_chain_id = give_chain_id
        self._take_chain_id = take_chain_id

    def get_type(self) -> str:
        return 'cross_chain'

    @property
    def give_chain_id(self) -> int:
        return self._give_chain_id

    @property
    def take_chain_id(self) -> int:
        return self._take_chain_id

