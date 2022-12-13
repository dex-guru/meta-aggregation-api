import json
import os
from pathlib import Path

import pytest
from jsonschema import validate

SCHEMA_NAME = 'provider_config.schema.json'
CLIENTS_PATH = 'provider_clients'


@pytest.fixture()
def get_schema():
    with open(Path('tests', CLIENTS_PATH, SCHEMA_NAME)) as f:
        return json.load(f)


def test_validate_config_schema(get_schema):
    for path, subdirs, files in os.walk(CLIENTS_PATH):
        for file in files:
            if 'config.json' in file:
                with open(Path(path, file)) as f:
                    token_list = json.load(f)
                    validate(token_list, get_schema)
