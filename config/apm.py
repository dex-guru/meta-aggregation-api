from pydantic import BaseSettings, HttpUrl


class APMConfig(BaseSettings):
    APM_SERVER_URL: HttpUrl = 'https://apm-stage-lax.dexguru.biz:443'
    SERVICE_NAME: str = 'UNSPECIFIED SERVICE'
    APM_ENABLED: bool = False
    APM_RECORDING: bool = False
    APM_CAPTURE_HEADERS: bool = False
    LOG_LEVEL: str = 'off'
    ENVIRONMENT: str = 'dev'
