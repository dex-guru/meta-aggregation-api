from config.apm import APMConfig
from config.logger import LoggerConfig
from config.chains import ChainsConfig
from utils.common import Singleton
from config.chains import chains


class Config(APMConfig, LoggerConfig, metaclass=Singleton):
    SERVER_HOST: str = 'http://localhost:8000'
    IS_DEBUG: bool = True
    PIPELINE: str = 'stage'
    NATIVE_TOKEN_ADDRESS = '0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'
    VERSION = '0.0.1'


config = Config()
