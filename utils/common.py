import re
from urllib.parse import urljoin

from pydantic import constr

from config import config


def _camel_to_snake(field: str) -> str:
    field = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', field)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', field).lower()


def get_web3_url(chain_id: int):
    return urljoin(config.WEB3_URL, f'{chain_id}/{config.PUBLIC_KEY}')


address_to_lower = constr(strip_whitespace=True, min_length=42, max_length=42, to_lower=True)
