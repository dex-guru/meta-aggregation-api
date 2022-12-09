import pytest

from utils.httputils import setup_client_session, teardown_client_session


@pytest.fixture()
@pytest.mark.asyncio
async def aiohttp_session():
    await setup_client_session()
    from utils.httputils import CLIENT_SESSION
    yield CLIENT_SESSION
    await teardown_client_session()
