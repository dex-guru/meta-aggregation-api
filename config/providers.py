from pathlib import Path

import ujson

from utils import Singleton


class ProvidersConfig(metaclass=Singleton):
    providers: dict = ...

    def __init__(self) -> None:
        with open(Path(__file__).parent / 'providers_config.json') as f:
            self.providers = ujson.load(f)


providers = ProvidersConfig()
