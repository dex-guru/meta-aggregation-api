from typing import TypeVar

from meta_aggregation_api.providers.base_provider import BaseProvider

T = TypeVar("T")


class ProviderRegistry:
    def __init__(self, *providers: BaseProvider):
        self.providers_by_name = {
            provider.PROVIDER_NAME: provider for provider in providers
        }

    def __getitem__(self, provider_name: str) -> BaseProvider:
        return self.providers_by_name[provider_name]

    def get(self, provider_name: str, default: T = None) -> BaseProvider | T:
        return self.providers_by_name.get(provider_name, default)
