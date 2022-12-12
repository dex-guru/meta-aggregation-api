from dexguru_sdk import DexGuru
from pydantic import HttpUrl

from models.chain import ChainModel
from utils import Singleton


class ChainsConfig(metaclass=Singleton):
    """
    All supported chains are defined here.
    Chain object contains name, chain_id, description and native_token.
    Native token is an object with address, name, symbol and decimals.
    Models defined in models/chain.py

    Usage:
        from config import chains

        chain = chains.eth
        chain.chain_id
        # 1
    """

    async def set_chains(self, api_key: str, domain: HttpUrl):
        chains_ = await DexGuru(api_key=api_key, domain=domain).get_chains()
        for chain in chains_.data:
            self.__dict__[chain.name.lower()] = ChainModel.parse_obj(chain.dict())

    def __contains__(self, item: str | int):
        return item in self.__dict__.keys() or item in [chain.chain_id for chain in self.__dict__.values()]

    def get_chain_by_id(self, chain_id: int):
        for chain in self.__dict__.values():
            if chain.chain_id == chain_id:
                return chain
        raise ValueError(f'Chain id {chain_id} not found')


chains = ChainsConfig()
