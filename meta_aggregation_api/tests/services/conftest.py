import aiohttp
import pytest

from meta_aggregation_api.config.providers import ProvidersConfig
from meta_aggregation_api.services.gas_service import GasService
from meta_aggregation_api.services.meta_aggregation_service import (
    MetaAggregationService,
)


@pytest.fixture
async def gas_service(config, chains):
    service = GasService(config=config, chains=chains)
    await service.cached.cache.clear()
    return service


@pytest.fixture
def providers():
    return ProvidersConfig()


@pytest.fixture
async def meta_agg_service(
    config,
    chains,
    gas_service: GasService,
    providers,
    apm_client,
) -> MetaAggregationService:
    service = MetaAggregationService(
        config=config,
        chains=chains,
        gas_service=gas_service,
        providers=providers,
        session=aiohttp.ClientSession(),
        apm_client=apm_client,
    )
    return service
