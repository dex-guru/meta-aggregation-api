import pytest
from starlette.testclient import TestClient

from meta_aggregation_api.config import config, providers
from meta_aggregation_api.models.chain import ChainModel, TokenModel
from meta_aggregation_api.rest_api.create_app import create_app
from meta_aggregation_api.services.chains import ChainsConfig
from meta_aggregation_api.tests.fixtures import *  # noqa: F401, F403


@pytest.fixture()
async def chains_fixture():
    chains = ChainsConfig(config.PUBLIC_KEY, config.PUBLIC_API_DOMAIN)
    chains.chains = {
        'eth': ChainModel(
            name='eth',
            chain_id=1,
            description='Ethereum',
            eip1559=True,
            native_token=TokenModel(
                address='0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2',
                decimals=18,
                name='Wrapped Ether',
                symbol='WETH',
            ),
        ),
        'bsc': ChainModel(
            name='bsc',
            chain_id=56,
            description='Binance Smart Chain',
            eip1559=False,
            native_token=TokenModel(
                address='0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c',
                decimals=18,
                name='Wrapped BNB',
                symbol='WBNB',
            ),
        ),
    }
    return chains


@pytest.fixture()
def trading_client(chains_fixture) -> TestClient:
    app = create_app(config=config)
    app.chains = chains_fixture
    app.providers = providers
    return TestClient(app)
