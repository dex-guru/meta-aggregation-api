from dexguru_sdk import DexGuru
from pydantic import HttpUrl

from meta_aggregation_api.config import config
from meta_aggregation_api.models.chain import ChainModel
from meta_aggregation_api.utils.singleton import Singleton


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

    chains = {}

    def __init__(self, api_key: str, domain: HttpUrl):
        self.dex_guru_sdk = DexGuru(api_key=api_key, domain=domain)

    async def set_chains(self):
        chains_ = await self.dex_guru_sdk.get_chains()
        for chain in chains_.data:
            self.chains[chain.name.lower()] = ChainModel.parse_obj(chain.dict())

    def __contains__(self, item: str | int):
        return item in self.chains.keys() or item in [
            chain.chain_id for chain in self.__dict__.values()
        ]

    def get_chain_by_id(self, chain_id: int):
        for chain in self.chains.values():
            if chain.chain_id == chain_id:
                return chain
        raise ValueError(f'Chain id {chain_id} not found')

    def __getattr__(self, item):
        return self.chains[item]


chains = ChainsConfig(api_key=config.PUBLIC_KEY, domain=config.PUBLIC_API_DOMAIN)
