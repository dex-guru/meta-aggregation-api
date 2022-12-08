from pathlib import Path

import ujson

from utils import Singleton


class ProvidersConfig(metaclass=Singleton):

    def __init__(self) -> None:
        with open(Path(__file__).parent / 'providers_config.json') as f:
            providers = ujson.load(f)
            for chain, info in providers.items():
                self.__dict__[str(chain)] = info

    def get(self, chain: int) -> dict:
        return self.__dict__[str(chain)]


providers = ProvidersConfig()
