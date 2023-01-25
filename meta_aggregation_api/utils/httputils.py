import os

from aiohttp import ClientSession

# Singleton aiohttp.ClientSession instance.
CLIENT_SESSION: ClientSession


class CustomHttpSession(ClientSession):
    """
    Custom aiohttp.ClientSession that adds proxy for requests.
    We can't use `trust_env=True` because it will also use proxy for APM requests.
    """

    async def _request(self, *args, **kwargs):
        proxy = kwargs.pop('proxy', os.environ.get('PROXY_URL'))
        return await super()._request(proxy=proxy, *args, **kwargs)


async def setup_client_session() -> None:
    """Set up the application-global aiohttp.ClientSession instance.

    aiohttp recommends that only one ClientSession exist for the lifetime of an application.
    See: https://docs.aiohttp.org/en/stable/client_quickstart.html#make-a-request

    """
    global CLIENT_SESSION  # pylint: disable=global-statement
    CLIENT_SESSION = CustomHttpSession()


async def teardown_client_session() -> None:
    """Close the application-global aiohttp.ClientSession."""
    global CLIENT_SESSION  # pylint: disable=global-statement
    await CLIENT_SESSION.close()
