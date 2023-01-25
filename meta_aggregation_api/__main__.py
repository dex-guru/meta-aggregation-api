import logging.config

import uvicorn

from meta_aggregation_api.config import Config
from meta_aggregation_api.rest_api.create_app import create_app
from meta_aggregation_api.utils import logger


def __getattr__(name):
    if name == 'app':
        config = Config()
        logging.config.dictConfig(logger.config(config))
        app = create_app(config)
        return app

    raise AttributeError(name)


def main() -> None:
    """Entrypoint of the application."""
    config = Config()
    uvicorn.run(
        'meta_aggregation_api.__main__:app',
        workers=config.WORKERS_COUNT,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        reload=config.RELOAD,
        log_level=config.LOGGING_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
