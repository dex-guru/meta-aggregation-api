import os
from pathlib import Path

import ujson

from meta_aggregation_api.utils.singleton import Singleton


class ProvidersConfig(metaclass=Singleton):

    def __init__(self) -> None:
        for path, _, files in os.walk('providers'):
            for file in files:
                if 'config.json' == file:
                    with open(Path(path, file)) as f:
                        provider_config = ujson.load(f)
                        self.__dict__[provider_config['name']] = provider_config
                        for spender in provider_config['spenders']:
                            self.__dict__[provider_config['name']][spender['chain_id']] = spender
                        self.__dict__[provider_config['name']].pop('spenders')

    def __iter__(self):
        return iter(self.__dict__)

    def items(self):
        return self.__dict__.items()

    def keys(self):
        return self.__dict__.keys()

    def values(self):
        return self.__dict__.values()

    def get_providers_by_chain(self, chain_id: int) -> dict:
        providers_by_chain = {
            'market_order': [],
            'limit_order': [],
        }
        for provider in self.values():
            if chain_id in provider:
                if provider[chain_id]['market_order']:
                    providers_by_chain['market_order'].append({
                        'display_name': provider['display_name'],
                        'address': provider[chain_id]['market_order'],
                        'name': provider['name'],
                    })
                if provider[chain_id]['limit_order']:
                    providers_by_chain['limit_order'].append({
                        'display_name': provider['display_name'],
                        'address': provider[chain_id]['limit_order'],
                        'name': provider['name'],
                    })
        if not providers_by_chain['market_order'] and not providers_by_chain['limit_order']:
            raise ValueError(f'Chain ID {chain_id} not found')
        return providers_by_chain


providers = ProvidersConfig()
