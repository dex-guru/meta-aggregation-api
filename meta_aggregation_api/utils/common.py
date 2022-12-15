import re
from urllib.parse import urljoin

from meta_aggregation_api.config import config


def _camel_to_snake(field: str) -> str:
    field = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', field)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', field).lower()


def get_web3_url(chain_id: int):
    return urljoin(config.WEB3_URL, f'{chain_id}/{config.PUBLIC_KEY}')
