import pytest

from meta_aggregation_api.providers.debridge_dln_v1 import DebridgeDlnProviderV1
from meta_aggregation_api.providers.one_inch_v5.one_inch_provider import (
    OneInchProviderV5,
)
from meta_aggregation_api.providers.paraswap_v5.paraswap_provider_v5 import (
    ParaSwapProviderV5,
)
from meta_aggregation_api.providers.zerox_v1.zerox_provider import ZeroXProviderV1


@pytest.fixture()
def one_inch_provider(aiohttp_session, config, apm_client):
    return OneInchProviderV5(
        session=aiohttp_session, config=config, apm_client=apm_client
    )


@pytest.fixture()
def zerox_provider(aiohttp_session, config, chains, apm_client):
    return ZeroXProviderV1(
        session=aiohttp_session, config=config, chains=chains, apm_client=apm_client
    )


@pytest.fixture()
def paraswap_provider(aiohttp_session, config, apm_client):
    return ParaSwapProviderV5(
        session=aiohttp_session, config=config, apm_client=apm_client
    )

@pytest.fixture()
def debridge_provider(aiohttp_session, config, apm_client):
    return DebridgeDlnProviderV1(
        session=aiohttp_session, config=config, apm_client=apm_client
    )
