from pydantic import BaseModel

from meta_aggregation_api.utils.common import camel_to_snake


class SwapSources(BaseModel):
    name: str
    proportion: float  # Percentage.

    def __init__(self, **data):
        data['name'] = camel_to_snake(data['name'])
        data['name'] = ''.join(word.capitalize() for word in data['name'].split('_'))
        super().__init__(**data)
