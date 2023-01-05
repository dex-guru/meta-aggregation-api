from aiohttp import ClientSession

# Singleton aiohttp.ClientSession instance.
CLIENT_SESSION: ClientSession


async def setup_client_session() -> None:
    """Set up the application-global aiohttp.ClientSession instance.

    aiohttp recommends that only one ClientSession exist for the lifetime of an application.
    See: https://docs.aiohttp.org/en/stable/client_quickstart.html#make-a-request

    """
    global CLIENT_SESSION  # pylint: disable=global-statement
    CLIENT_SESSION = ClientSession(trust_env=True)


async def teardown_client_session() -> None:
    """Close the application-global aiohttp.ClientSession.
    """
    global CLIENT_SESSION  # pylint: disable=global-statement
    await CLIENT_SESSION.close()
