import re


def _camel_to_snake(field: str) -> str:
    field = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', field)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', field).lower()
