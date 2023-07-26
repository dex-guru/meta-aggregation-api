import aiohttp
import pytest

from meta_aggregation_api.config.providers import ProvidersConfig
from meta_aggregation_api.providers import ProviderRegistry
from meta_aggregation_api.providers.debridge_dln_v1 import DebridgeDlnProviderV1
from meta_aggregation_api.providers.kyberswap_v1 import KyberSwapProviderV1
from meta_aggregation_api.providers.one_inch_v5 import OneInchProviderV5
from meta_aggregation_api.providers.openocean_v2 import OpenOceanProviderV2
from meta_aggregation_api.providers.paraswap_v5 import ParaSwapProviderV5
from meta_aggregation_api.providers.zerox_v1 import ZeroXProviderV1
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
    provider_registry,
) -> MetaAggregationService:
    service = MetaAggregationService(
        config=config,
        chains=chains,
        gas_service=gas_service,
        providers=providers,
        session=aiohttp.ClientSession(),
        apm_client=apm_client,
        provider_registry=provider_registry,
        crosschain_provider_registry=provider_registry,
    )
    return service


@pytest.fixture
def provider_registry(config, chains, apm_client, aiohttp_session):
    return ProviderRegistry(
        ZeroXProviderV1(
            session=aiohttp_session,
            config=config,
            chains=chains,
            apm_client=apm_client,
        ),
        OneInchProviderV5(
            config=config,
            session=aiohttp_session,
            apm_client=apm_client,
        ),
        ParaSwapProviderV5(
            config=config,
            session=aiohttp_session,
            apm_client=apm_client,
        ),
        OpenOceanProviderV2(
            config=config,
            session=aiohttp_session,
            apm_client=apm_client,
        ),
        KyberSwapProviderV1(
            config=config,
            session=aiohttp_session,
            apm_client=apm_client,
            chains=chains,
        ),
        DebridgeDlnProviderV1(
            config=config,
            session=aiohttp_session,
            apm_client=apm_client,
            chains=chains,
        ),
    )
