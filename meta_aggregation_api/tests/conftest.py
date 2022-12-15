import pytest
from starlette.testclient import TestClient

from meta_aggregation_api.rest_api.create_app import create_app
from meta_aggregation_api.config import config, providers
from meta_aggregation_api.services.chains import chains
from meta_aggregation_api.tests.fixtures import *  # noqa: F401, F403


@pytest.fixture()
def trading_client() -> TestClient:
    app = create_app(config=config)
    app.chains = chains
    app.providers = providers
    return TestClient(app)
