import requests
from pydantic import BaseSettings

from models.chain import ChainModel


class ChainsConfig(BaseSettings):

    def __init__(self, **data):
        self.get_chains()
        super().__init__(**data)

    def get_chains(self):
        chains = requests.get('https://api.dev.dex.guru/v1/chain').json()
        for chain in chains['data']:
            self.__setattr__(chain['name'].lower(), ChainModel(**chain['chain_id']))
