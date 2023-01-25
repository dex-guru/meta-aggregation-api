import uvicorn

from meta_aggregation_api.config import config
from meta_aggregation_api.rest_api.create_app import create_app

app = create_app(config)


def main() -> None:
    """Entrypoint of the application."""
    uvicorn.run(
        "meta_aggregation_api.__main__:app",
        workers=config.WORKERS_COUNT,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        reload=config.RELOAD,
        log_level=config.LOGGING_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
