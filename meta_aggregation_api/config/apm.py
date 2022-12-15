from pydantic import BaseSettings


class APMConfig(BaseSettings):
    APM_SERVER_URL: str = 'http://localhost:8200'
    SERVICE_NAME: str = 'meta-aggregation-api'
    APM_ENABLED: bool = False
    APM_RECORDING: bool = False
    APM_CAPTURE_HEADERS: bool = False
    LOG_LEVEL: str = 'off'
    ENVIRONMENT: str = 'dev'
