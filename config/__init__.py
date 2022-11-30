from config.apm import APMConfig
from config.chains import ChainsConfig
from config.chains import chains
from config.logger import LoggerConfig
from config.providers_config import ProvidersConfig


class Config(APMConfig, LoggerConfig, ProvidersConfig):
    SERVER_HOST: str = 'http://localhost:8000'
    IS_DEBUG: bool = True
    PIPELINE: str = 'stage'
    NATIVE_TOKEN_ADDRESS = '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'
    VERSION = '0.0.1'
    WEB3_URL = 'http://10.0.100.101:8545'
    API_KEY = ''
    PUBLIC_API_VERSION = 1
    WEB3_TIMEOUT: int = 10


config = Config()
