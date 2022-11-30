import requests

from models.chain import ChainModel
from utils.common import Singleton


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

    def __init__(self):
        self._set_chains()

    def _set_chains(self):
        chains = requests.get('http://localhost:8001/v1/chain').json()
        for chain in chains['data']:
            self.__dict__[chain['name'].lower()] = ChainModel(**chain)

    def __contains__(self, item: str | int):
        return item in self.__dict__.keys() or item in [chain.chain_id for chain in self.__dict__.values()]

    def get_chain_by_id(self, chain_id: int):
        for chain in self.__dict__.values():
            if chain.chain_id == chain_id:
                return chain
        raise ValueError(f'Chain with id {chain_id} not found')


chains = ChainsConfig()
