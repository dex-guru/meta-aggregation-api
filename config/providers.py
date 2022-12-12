from pathlib import Path

import ujson

from utils.singleton import Singleton


class ProvidersConfig(metaclass=Singleton):

    def __init__(self) -> None:
        with open(Path(__file__).parent / 'providers_config.json') as f:
            providers = ujson.load(f)
            for chain, info in providers.items():
                self.__dict__[str(chain)] = info

    def __iter__(self):
        return iter(self.__dict__.keys())

    def get(self, chain_id: int) -> dict:
        chain = self.__dict__.get(str(chain_id))
        if not chain:
            raise ValueError(f'Chain ID {chain_id} not found')
        return chain


providers = ProvidersConfig()
