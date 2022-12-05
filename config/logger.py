from typing import List

from pydantic import BaseSettings


class LoggerConfig(BaseSettings):
    LOGGING_LEVEL: str = 'INFO'
    LOGSTASH_LOGGING_LEVEL: str = 'DEBUG'
    LOG_HANDLERS: List[str] = ['console']
    LOGSTASH: str = 'logstash-logstash.logging.svc.cluster.local'  # TODO: probably for local development we need logstash running from docker-compose
    PORT: int = 5959
