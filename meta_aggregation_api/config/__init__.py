from meta_aggregation_api.config.apm import APMConfig
from meta_aggregation_api.config.logger import LoggerConfig
from meta_aggregation_api.config.providers import providers


class Config(APMConfig, LoggerConfig):
    SERVER_HOST: str = 'localhost'
    SERVER_PORT: int = 8000
    RELOAD: bool = True
    NATIVE_TOKEN_ADDRESS = '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'
    VERSION = '0.0.1'
    WEB3_URL = 'https://api-proxy-stage-lax.dexguru.biz'
    # generate key at https://developers.dex.guru/
    PUBLIC_KEY = 'GoQ7lSlHLwC9NyLzfFt0LcRjdjwOIkRhOTtjcy55t2o'
    PUBLIC_API_DOMAIN = 'https://public-stage-lax.dexguru.biz'
    API_VERSION = 1
    WEB3_TIMEOUT: int = 10
    X_SYS_KEY = 'vd399tVUdU4y'
    CORS_ORIGINS = ['*']
    CORS_CREDENTIALS = True
    CORS_METHODS = ['*']
    CORS_HEADERS = ['*']
    WORKERS_COUNT: int = 1

config = Config()
