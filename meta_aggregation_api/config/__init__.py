from urllib.parse import urljoin

from pydantic import BaseSettings, HttpUrl

from meta_aggregation_api.config.apm import APMConfig
from meta_aggregation_api.config.auth import AuthConfig
from meta_aggregation_api.config.cache import CacheConfig
from meta_aggregation_api.config.logger import LoggerConfig


class Config(APMConfig, LoggerConfig, AuthConfig, CacheConfig, BaseSettings):
    SERVER_HOST: str = 'localhost'
    SERVER_PORT: int = 8000
    RELOAD: bool = True
    NATIVE_TOKEN_ADDRESS = '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'
    VERSION = '0.0.1'
    PUBLIC_KEY = 'Get your key at https://developers.dex.guru'
    PUBLIC_API_DOMAIN: HttpUrl = 'https://api.dev.dex.guru'
    API_VERSION = 1
    WEB3_TIMEOUT: int = 10
    CORS_ORIGINS = ['*']
    CORS_CREDENTIALS = True
    CORS_METHODS = ['*']
    CORS_HEADERS = ['*']
    WORKERS_COUNT: int = 1
    PARTNER: str = 'dex.guru'
    X_SYS_KEY: str = ''
    ONE_INCH_API_KEY: str = ''

    def get_web3_url(self, chain_id: int):
        return urljoin(self.PUBLIC_API_DOMAIN, f'{chain_id}/{self.PUBLIC_KEY}')

    class Config:
        env_file = ".env"
