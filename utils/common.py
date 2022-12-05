import re
from urllib.parse import urljoin

from config import config


def _camel_to_snake(field: str) -> str:
    field = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', field)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', field).lower()


def get_web3_url(chain_id: int):
    return urljoin(config.WEB3_URL, f'{chain_id}/{config.PUBLIC_KEY}')


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
