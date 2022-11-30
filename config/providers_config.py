from typing import Any

import ujson
from pydantic import BaseSettings


class ProvidersConfig(BaseSettings):
    providers: dict = ujson.loads(open('config/providers_config.json', 'r').read())

    # def __init__(self, **data: Any) -> None:
    #     with open('config/providers_config.json', 'r') as f:
    #         self.providers = ujson.load(f)
    #     super().__init__(**data)
