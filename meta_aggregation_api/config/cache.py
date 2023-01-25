from pydantic import BaseSettings


class CacheConfig(BaseSettings):
    CACHE: str = 'memory'
    CACHE_HOST: str = '127.0.0.1'
    CACHE_PORT: int = 6379
    CACHE_DB: int = 0
    CACHE_PASSWORD: str = None
    CACHE_TIMEOUT: float = 30
