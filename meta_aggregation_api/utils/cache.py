from aiocache import Cache
from aiocache.serializers import PickleSerializer

from meta_aggregation_api.config import config

CACHE_CONFIG_COMMON_REDIS = {
    'cache': Cache.REDIS,
    'endpoint': config.CACHE_HOST,
    'port': config.CACHE_PORT,
    'serializer': PickleSerializer(),
    'db': config.CACHE_DB,
    'password': config.CACHE_PASSWORD,
    "timeout": config.CACHE_TIMEOUT,
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
