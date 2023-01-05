from enum import Enum
from hashlib import md5

from aiocache import Cache
from aiocache.serializers import PickleSerializer
from starlette.requests import Request
from web3.contract import AsyncContract

from meta_aggregation_api.config import config


def key_from_args(func, *args, **kwargs):
    filtered_args = []
    for arg in args:
        if isinstance(arg, Enum):
            filtered_args.append(arg.value)
        elif isinstance(arg, AsyncContract):
            filtered_args.append(arg.address)
        elif isinstance(arg, Request):
            continue
        elif hasattr(arg, 'PROVIDER_NAME'):
            filtered_args.append(arg.PROVIDER_NAME)
        filtered_args.append(arg)

    if kwargs.get('request'):
        kwargs.pop('request')
    ordered_kwargs = sorted(kwargs.items())
    key = (
            (func.__module__ or "")
            + func.__name__
            + str(filtered_args)
            + str(ordered_kwargs)
    )
    md5_hash = md5(key.encode()).digest()
    return md5_hash


CACHE_CONFIG_COMMON_REDIS = {
    'cache': Cache.REDIS,
    'endpoint': config.CACHE_HOST,
    'port': config.CACHE_PORT,
    'serializer': PickleSerializer(),
    'key_builder': key_from_args,
    'db': config.CACHE_DB,
    'password': config.CACHE_PASSWORD,
    'timeout': config.CACHE_TIMEOUT,
}


CACHE_CONFIG_COMMON_MEMORY = {
    'cache': Cache.MEMORY,
}

CACHE_CONFIG = {
    'memory': CACHE_CONFIG_COMMON_MEMORY,
    'redis': CACHE_CONFIG_COMMON_REDIS,
}


def get_cache_config() -> dict:
    return CACHE_CONFIG[config.CACHE]
