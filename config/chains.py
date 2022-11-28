import requests
from pydantic import BaseSettings

from models.chain import ChainModel


class ChainsConfig(BaseSettings):

    def __init__(self, **data):
        super().__init__(**data)
        self._set_chains()

    def _set_chains(self):
        chains = requests.get('https://api.dev.dex.guru/v1/chain').json()
        for chain in chains['data']:
            self.__dict__[chain['name'].lower()] = ChainModel(**chain)
