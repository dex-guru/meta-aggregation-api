from config.apm import APMConfig
from config.logger import LoggerConfig
from config.chains import ChainsConfig


class Config(APMConfig, LoggerConfig, ChainsConfig):
    SERVER_HOST: str = 'http://localhost:8000'
    IS_DEBUG: bool = True
    PIPELINE: str = 'stage'
    NATIVE_TOKEN_ADDRESS = '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'
    VERSION = '0.0.1'


config = Config()
