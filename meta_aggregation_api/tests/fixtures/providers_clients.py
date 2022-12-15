import pytest

from meta_aggregation_api.providers.one_inch_v5.one_inch_provider import OneInchProviderV5
from meta_aggregation_api.providers.paraswap_v5.paraswap_provider_v5 import ParaSwapProviderV5
from meta_aggregation_api.providers.zerox_v1.zerox_provider import ZeroXProviderV1


@pytest.fixture()
def one_inch_provider(aiohttp_session):
    from meta_aggregation_api.utils.httputils import CLIENT_SESSION
    return OneInchProviderV5(CLIENT_SESSION)


@pytest.fixture()
def zerox_provider(aiohttp_session):
    from meta_aggregation_api.utils.httputils import CLIENT_SESSION
    return ZeroXProviderV1(CLIENT_SESSION)


@pytest.fixture()
def paraswap_provider(aiohttp_session):
    from meta_aggregation_api.utils.httputils import CLIENT_SESSION
    return ParaSwapProviderV5(CLIENT_SESSION)
