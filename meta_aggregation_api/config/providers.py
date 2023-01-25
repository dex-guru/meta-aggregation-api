import os
from collections import defaultdict
from pathlib import Path

import ujson


class ProvidersConfig:
    def __init__(self) -> None:
        for path, _, files in os.walk(Path(__file__).parent.parent / 'providers'):
            for file in files:
                if 'config.json' == file:
                    with open(Path(path, file)) as f:
                        provider_config = ujson.load(f)
                        if not provider_config.get('enabled'):
                            continue
                        self.__dict__[provider_config['name']] = provider_config
                        for spender in provider_config['spenders']:
                            self.__dict__[provider_config['name']][
                                spender['chain_id']
                            ] = spender
                        self.__dict__[provider_config['name']].pop('spenders')

    def __iter__(self):
        return iter(self.__dict__)

    def items(self):
        return self.__dict__.items()

    def keys(self):
        return self.__dict__.keys()

    def values(self):
        return self.__dict__.values()

    def get_providers_on_chain(self, chain_id: int) -> dict:
        providers_on_chain = {
            'market_order': [],
            'limit_order': [],
        }
        for provider in self.values():
            if chain_id in provider:
                if provider[chain_id]['market_order']:
                    providers_on_chain['market_order'].append(
                        {
                            'display_name': provider['display_name'],
                            'address': provider[chain_id]['market_order'],
                            'name': provider['name'],
                        }
                    )
                if provider[chain_id]['limit_order']:
                    providers_on_chain['limit_order'].append(
                        {
                            'display_name': provider['display_name'],
                            'address': provider[chain_id]['limit_order'],
                            'name': provider['name'],
                        }
                    )
        if (
            not providers_on_chain['market_order']
            and not providers_on_chain['limit_order']
        ):
            raise ValueError(f'Chain ID {chain_id} not found')
        return providers_on_chain

    def get_all_providers(self) -> list[dict]:
        provider_on_chains = defaultdict(
            lambda: defaultdict(limit_order=[], market_order=[])
        )
        for provider in self.values():
            for chain in provider.values():
                if not isinstance(chain, dict):
                    continue

                if chain.get('market_order'):
                    provider_on_chains[chain['chain_id']]['market_order'].append(
                        {
                            'display_name': provider['display_name'],
                            'address': chain['market_order'],
                            'name': provider['name'],
                        }
                    )
                if chain.get('limit_order'):
                    provider_on_chains[chain['chain_id']]['limit_order'].append(
                        {
                            'display_name': provider['display_name'],
                            'address': chain['limit_order'],
                            'name': provider['name'],
                        }
                    )
        return [
            {'chain_id': chain, **item} for chain, item in provider_on_chains.items()
        ]
