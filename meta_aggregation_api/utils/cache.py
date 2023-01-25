from enum import Enum
from hashlib import md5

from aiocache import Cache
from aiocache.serializers import PickleSerializer
from starlette.requests import Request
from web3.contract import AsyncContract

from meta_aggregation_api.config import CacheConfig


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


def get_cache_config(config: CacheConfig) -> dict:
    cache_config_common_redis = {
        'cache': Cache.REDIS,
        'endpoint': config.CACHE_HOST,
        'port': config.CACHE_PORT,
        'serializer': PickleSerializer(),
        'key_builder': key_from_args,
        'db': config.CACHE_DB,
        'password': config.CACHE_PASSWORD,
        'timeout': config.CACHE_TIMEOUT,
    }

    cache_config_common_memory = {
        'cache': Cache.MEMORY,
    }

    cache_config = {
        'memory': cache_config_common_memory,
        'redis': cache_config_common_redis,
    }

    return cache_config[config.CACHE]
