from typing import Optional

from elasticapm.base import Client
from elasticapm.contrib.starlette import make_apm_client

from meta_aggregation_api.config import Config


class ApmClient:
    def __init__(self, config: Config):
        self.client: Optional[Client] = None
        self._make_apm_client(config)

    def _make_apm_client(self, config: Config) -> Client:
        if self.client:
            return self.client
        apm_config = {
            'SERVICE_NAME': config.SERVICE_NAME,
            'SERVER_URL': config.APM_SERVER_URL,
            'ENABLED': config.APM_ENABLED,
            'RECORDING': config.APM_RECORDING,
            'CAPTURE_HEADERS': config.APM_CAPTURE_HEADERS,
            'LOG_LEVEL': config.LOG_LEVEL,
            'ENVIRONMENT': config.ENVIRONMENT,
            'SERVICE_VERSION': config.VERSION,
        }
        self.client = make_apm_client(apm_config)
        return self.client
