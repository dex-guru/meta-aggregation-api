import json
import os
from pathlib import Path

import pytest
from jsonschema import validate

SCHEMA_NAME = 'provider_config.schema.json'
CLIENTS_PATH = 'providers'


@pytest.fixture()
def get_schema():
    with open(Path('tests', CLIENTS_PATH, SCHEMA_NAME)) as f:
        return json.load(f)


def test_validate_config_schema(get_schema):
    for path, subdirs, files in os.walk(CLIENTS_PATH):
        for file in files:
            if 'config.json' == file:
                with open(Path(path, file)) as f:
                    provider_config = json.load(f)
                    validate(provider_config, get_schema)
