import pytest

from provider_clients.one_inch_provider.one_inch_provider import OneInchProvider
from provider_clients.paraswap_provider_v5.paraswap_provider_v5 import ParaSwapProviderV5
from provider_clients.zerox_provider.zerox_provider import ZeroXProvider


@pytest.fixture()
def one_inch_provider(aiohttp_session):
    from utils.httputils import CLIENT_SESSION
    return OneInchProvider(CLIENT_SESSION)


@pytest.fixture()
def zerox_provider(aiohttp_session):
    from utils.httputils import CLIENT_SESSION
    return ZeroXProvider(CLIENT_SESSION)


@pytest.fixture()
def paraswap_provider(aiohttp_session):
    from utils.httputils import CLIENT_SESSION
    return ParaSwapProviderV5(CLIENT_SESSION)
