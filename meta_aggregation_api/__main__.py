import uvicorn

from meta_aggregation_api.rest_api.create_app import create_app
from meta_aggregation_api.config import config

app = create_app(config)


def main() -> None:
    """Entrypoint of the application."""
    uvicorn.run(
        "meta_aggregation_api_github.rest_api.create_app:create_app",
        workers=config.WORKERS_COUNT,
        host=config.HOST,
        port=config.PORT,
        reload=config.RELOAD,
        log_level=config.LOG_LEVEL.value.lower(),
        factory=True,
    )


if __name__ == "__main__":
    main()
