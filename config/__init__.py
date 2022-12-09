from config.apm import APMConfig
from config.chains import ChainsConfig
from config.logger import LoggerConfig
from config.providers import providers


class Config(APMConfig, LoggerConfig):
    SERVER_HOST: str = 'http://localhost:8000'
    IS_DEBUG: bool = True
    NATIVE_TOKEN_ADDRESS = '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'
    VERSION = '0.0.1'
    WEB3_URL = 'https://api-proxy-stage-lax.dexguru.biz'
    PUBLIC_KEY = 'default'
    PUBLIC_API_DOMAIN = 'http://localhost:8001'
    API_VERSION = 1
    WEB3_TIMEOUT: int = 10
    X_SYS_KEY = 'vd399tVUdU4y'
    CORS_ORIGINS = ['*']
    CORS_CREDENTIALS = True
    CORS_METHODS = ['*']
    CORS_HEADERS = ['*']


config = Config()
chains = ChainsConfig(config.PUBLIC_KEY, config.PUBLIC_API_DOMAIN)
