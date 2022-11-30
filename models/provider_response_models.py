from typing import List

from pydantic import BaseModel

from utils.common import _camel_to_snake


class SwapSources(BaseModel):
    name: str
    proportion: float  # Percentage.
    hops: List[str] = []  # TODO remove hops, split MultiHop for 0x

    def __init__(self, **data):
        data['name'] = _camel_to_snake(data['name'])
        data['name'] = ''.join(word.capitalize() for word in data['name'].split('_'))
        super().__init__(**data)


class SwapPriceResponse(BaseModel):
    provider: str  # AggregationProviderChoices
    sources: List
    buyAmount: str
    gas: str
    sellAmount: str
    gasPrice: str
    value: str
    price: str
