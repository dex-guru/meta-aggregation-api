import aiohttp
import pytest


@pytest.fixture
def aiohttp_session():
    return aiohttp.ClientSession()
