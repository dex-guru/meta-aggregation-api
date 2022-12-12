import pytest
from starlette.testclient import TestClient

from api.create_app import create_app
from config import config, providers
from services.chains import chains
from tests.fixtures import *  # noqa: F401, F403


@pytest.fixture()
def trading_client() -> TestClient:
    app = create_app(config=config)
    app.chains = chains
    app.providers = providers
    return TestClient(app)
