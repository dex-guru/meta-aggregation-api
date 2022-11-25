from pydantic import BaseSettings
from typing import List


class LoggerConfig(BaseSettings):
    LOGGING_LEVEL: str = 'INFO'
    LOGSTASH_LOGGING_LEVEL: str = 'DEBUG'
    LOG_HANDLERS: List[str] = ['console']
    LOGSTASH: str = 'logstash-logstash.logging.svc.cluster.local'
    PORT: int = 5959
