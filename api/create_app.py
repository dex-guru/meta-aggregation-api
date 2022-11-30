import pydantic
from elasticapm.contrib.starlette import ElasticAPM
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from api.middlewares import RouteLoggerMiddleware
from api.routes.info import info_route
from api.routes.rpc import v1_rpc
from api.routes.swap import swap_route
from clients.apm_client import apm_client
from config import Config
from utils.httputils import setup_client_session, teardown_client_session
from utils.logger import get_logger

logger = get_logger(__name__)


def create_app(config: Config):
    app = FastAPI(
        title='DexGuru Trading API',
        description=(
            ''  # TODO: add description
        ),
        version=config.VERSION,
        docs_url='/',
        redoc_url='/docs',
        # openapi_tags=config.TAGS_METADATA
    )
    # pass config object to application
    app.config = config

    register_cors(app)
    register_gzip(app)
    register_route(app)
    register_route_logging(app)
    register_elastic_apm(app)

    # Common RFC 5741 Exceptions handling, https://tools.ietf.org/html/rfc5741#section-2
    @app.exception_handler(Exception)
    async def http_exception_handler(request: Request, exc):
        exception_dict = {
            "type": "Internal Server Error",
            "title": exc.__class__.__name__,
            "instance": f"{config.SERVER_HOST}{request.url.path}",
            "detail": f"{exc.__class__.__name__} at {str(exc)} when executing {request.method} request"
        }
        logger.error("Exception when %s: %s", exception_dict["instance"], exception_dict["detail"])
        return JSONResponse(exception_dict, status_code=500)

    @app.exception_handler(pydantic.error_wrappers.ValidationError)
    async def handle_validation_error(
            request: Request, exc: pydantic.error_wrappers.ValidationError
    ):  # pylint: disable=unused-argument
        """
        Handles validation errors.
        """
        return JSONResponse({"message": exc.errors()}, status_code=422)

    @app.on_event("startup")
    async def startup_event():
        await setup_client_session()

    @app.on_event("shutdown")
    async def shutdown_event():
        await teardown_client_session()

    @app.get("/health_check", include_in_schema=False)
    def health_check():
        """
        Health check
        ---
        tags:
            - util
        responses:
            200:
                description: Returns "OK"
        """
        return Response("OK")

    return app


def register_cors(app: FastAPI):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"])


def register_gzip(app: FastAPI):
    app.add_middleware(
        GZipMiddleware,
        minimum_size=1000)


def register_route_logging(app: FastAPI):
    app.add_middleware(
        RouteLoggerMiddleware)


def register_elastic_apm(app: FastAPI):
    app_config: Config = app.config
    if app_config.APM_ENABLED:
        app.add_middleware(ElasticAPM, client=apm_client.client)


def register_route(app: FastAPI):
    app.include_router(v1_rpc, prefix="", tags=["RPC Requests"])
    app.include_router(info_route, prefix="/info", tags=["Info"])
    app.include_router(swap_route, prefix="/market", tags=["Swap"])
