from pydantic import BaseSettings


class LoggerConfig(BaseSettings):
    LOGGING_LEVEL: str = 'INFO'
    LOGSTASH_LOGGING_LEVEL: str = 'DEBUG'
    LOG_HANDLERS: list = ['console']
    LOGSTASH: str = 'logstash-logstash.logging.svc.cluster.local'
    PORT: int = 5959
