"""
Custom implementation of sync and async HTTP providers.
Majority of the code was copied and adapted from Web3 library.
"""
import ssl
import threading
from typing import Any

import requests
from aiohttp import ClientSession, TCPConnector
from eth_typing import URI
from lru import LRU
from requests.adapters import HTTPAdapter
from urllib3 import Retry
from web3 import AsyncHTTPProvider, HTTPProvider
from web3.types import RPCEndpoint, RPCResponse

from meta_aggregation_api.config import Config
from meta_aggregation_api.utils.logger import LogArgs, get_logger

_logger = get_logger(__name__)


def _on_session_evicted_from_cache(cache_key, session: requests.Session) -> None:
    session.close()
    log_args = {LogArgs.web3_url: cache_key, LogArgs.cache_size: len(_session_cache)}
    _logger.info(
        f"Closed http session: %({LogArgs.web3_url})s", log_args, extra=log_args
    )


def _on_async_session_evicted_from_cache(cache_key, session: ClientSession) -> None:
    session.close()
    log_args = {
        LogArgs.web3_url: cache_key,
        LogArgs.cache_size: len(_async_session_cache),
    }
    _logger.info(
        f"Closed async http session: %({LogArgs.web3_url})s", log_args, extra=log_args
    )


_session_cache_lock = threading.Lock()
_session_cache = LRU(100, callback=_on_session_evicted_from_cache)

_async_session_cache_lock = threading.Lock()
_async_session_cache = LRU(100, callback=_on_async_session_evicted_from_cache)


def _get_session(endpoint_uri: URI) -> requests.Session:
    cache_key = endpoint_uri
    if cache_key not in _session_cache:
        session = requests.Session()
        http_adapter = HTTPAdapter(
            max_retries=Retry(connect=5, read=3), pool_connections=32, pool_maxsize=32
        )
        session.mount("https://", http_adapter)
        session.mount("http://", http_adapter)
        with _session_cache_lock:
            _session_cache[cache_key] = session
            log_args = {
                LogArgs.web3_url: cache_key,
                LogArgs.cache_size: len(_session_cache),
            }
            _logger.info(
                f"Created http session: %({LogArgs.web3_url})s",
                log_args,
                extra=log_args,
            )

    return _session_cache[cache_key]


async def _get_async_session(endpoint_uri: URI) -> ClientSession:
    cache_key = endpoint_uri
    if cache_key not in _async_session_cache:
        connector = TCPConnector(limit=32)
        session = ClientSession(connector=connector, raise_for_status=True)
        # note: there is no retry support like in requests, see https://github.com/aio-libs/aiohttp/issues/3133
        with _async_session_cache_lock:
            _async_session_cache[cache_key] = session
            log_args = {
                LogArgs.web3_url: cache_key,
                LogArgs.cache_size: len(_async_session_cache),
            }
            _logger.info(
                f"Created async http session: %({LogArgs.web3_url})s",
                log_args,
                extra=log_args,
            )

    return _async_session_cache[cache_key]


def _make_post_request(
    endpoint_uri: URI,
    data: bytes,
    config: Config,
    *args: Any,
    **kwargs: Any,
) -> bytes:
    kwargs.setdefault("timeout", config.WEB3_TIMEOUT)
    session = _get_session(endpoint_uri)
    response = session.post(endpoint_uri, data=data, *args, **kwargs)
    response.raise_for_status()

    return response.content


async def _async_make_post_request(
    endpoint_uri: URI,
    data: bytes,
    config: Config,
    **kwargs: Any,
) -> bytes:
    kwargs.setdefault("timeout", config.WEB3_TIMEOUT)
    session = await _get_async_session(endpoint_uri)
    async with session.post(endpoint_uri, data=data, **kwargs) as response:
        response.raise_for_status()
        return await response.read()


class CustomHTTPProvider(HTTPProvider):
    def __init__(self, endpoint_uri: URI, config: Config, *args: Any, **kwargs: Any):
        super().__init__(endpoint_uri, *args, **kwargs)
        self.config = config

    def make_request(self, method: RPCEndpoint, params: Any) -> RPCResponse:
        self.logger.debug(
            "Making request HTTP. URI: %s, Method: %s", self.endpoint_uri, method
        )
        request_data = self.encode_rpc_request(method, params)
        raw_response = _make_post_request(
            self.endpoint_uri,
            request_data,
            self.config,
            **self.get_request_kwargs()
            # type: ignore # see to_dict decorator on the method
        )
        response = self.decode_rpc_response(raw_response)
        self.logger.debug(
            "Getting response HTTP. URI: %s, " "Method: %s, Response: %s",
            self.endpoint_uri,
            method,
            response,
        )
        return response


class AsyncCustomHTTPProvider(AsyncHTTPProvider):
    def __init__(self, endpoint_uri: URI, config: Config, *args: Any, **kwargs: Any):
        super().__init__(endpoint_uri, *args, **kwargs)
        self.config = config

    async def make_request(self, method: RPCEndpoint, params: Any) -> RPCResponse:
        self.logger.debug(
            "Making request HTTP. URI: %s, Method: %s", self.endpoint_uri, method
        )
        request_data = self.encode_rpc_request(method, params)
        raw_response = await _async_make_post_request(
            self.endpoint_uri,
            request_data,
            self.config,
            **self.get_request_kwargs(),
            # type: ignore # see to_dict decorator on the method
            ssl=ssl.SSLContext(),
        )
        response = self.decode_rpc_response(raw_response)
        self.logger.debug(
            "Getting response HTTP. URI: %s, " "Method: %s, Response: %s",
            self.endpoint_uri,
            method,
            response,
        )
        return response
