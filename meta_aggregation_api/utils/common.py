import re
from urllib.parse import urljoin

from pydantic import constr

from meta_aggregation_api.config import Config


def camel_to_snake(field: str) -> str:
    field = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', field)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', field).lower()


def get_web3_url(chain_id: int, config: Config):
    """
    get web3 url for chain_id
    By default, it uses public api domain from config, assuming that
    nodes for specific chains are proxied under /{chain_id/{public_key} routes
    please adjust to return correct web3 url for your setup if needed
    """
    return urljoin(config.PUBLIC_API_DOMAIN, f'rpc/{chain_id}/{config.PUBLIC_KEY}')


address_to_lower = constr(
    strip_whitespace=True, to_lower=True
)
