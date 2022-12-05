from config.apm import APMConfig
from config.chains import ChainsConfig
from config.chains import chains
from config.logger import LoggerConfig
from config.providers_config import ProvidersConfig


class Config(APMConfig, LoggerConfig, ProvidersConfig):
    SERVER_HOST: str = 'http://localhost:8000'
    IS_DEBUG: bool = True
    PIPELINE: str = 'stage'                                 # TODO: remove as redundant ("pipeline" is for workers)
    NATIVE_TOKEN_ADDRESS = '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'
    VERSION = '0.0.1'
    WEB3_URL = 'https://api-proxy-stage-lax.dexguru.biz'    # TODO: consider to refer public resources
    API_KEY = 'default'                                     # TODO: document configuration in README and here
    PUBLIC_API_VERSION = 1
    WEB3_TIMEOUT: int = 10
    X_SYS_KEY = 'default'                                   # TODO: documentation is needed (do we use it?)


config = Config()
