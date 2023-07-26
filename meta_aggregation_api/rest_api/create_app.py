import aiohttp
import pydantic
from elasticapm.contrib.starlette import ElasticAPM
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi_jwt_auth.exceptions import AuthJWTException

from meta_aggregation_api.clients.apm_client import ApmClient
from meta_aggregation_api.config import Config
from meta_aggregation_api.providers import ProviderRegistry
from meta_aggregation_api.providers.debridge_dln_v1 import DebridgeDlnProviderV1
from meta_aggregation_api.providers.kyberswap_v1 import KyberSwapProviderV1
from meta_aggregation_api.providers.one_inch_v5 import OneInchProviderV5
from meta_aggregation_api.providers.openocean_v2 import OpenOceanProviderV2
from meta_aggregation_api.providers.paraswap_v5 import ParaSwapProviderV5
from meta_aggregation_api.providers.zerox_v1 import ZeroXProviderV1
from meta_aggregation_api.rest_api import dependencies
from meta_aggregation_api.rest_api.middlewares import RouteLoggerMiddleware
from meta_aggregation_api.rest_api.routes.gas import gas_routes
from meta_aggregation_api.rest_api.routes.info import info_route
from meta_aggregation_api.rest_api.routes.limit_orders import limit_orders
from meta_aggregation_api.rest_api.routes.rpc import v1_rpc
from meta_aggregation_api.rest_api.routes.swap import swap_route
from meta_aggregation_api.rest_api.routes.crosschain_swap import crosschain_swap_route
from meta_aggregation_api.utils.errors import BaseAggregationProviderError
from meta_aggregation_api.utils.logger import get_logger

logger = get_logger(__name__)


def create_app(config: Config):
    app = FastAPI(
        title='DexGuru Trading API',
        description=(
            """API serves as a DEX aggregators gateway and bargains finder (best quote) between assets and provides
            unified interface wrapping up differences between different aggregators.
            User request price, getting sorted list of quotes and bargain calcs,
            and can request a quote (with tx data included) for selected bargain."""
        ),
        version=config.VERSION,
        docs_url='/',
        redoc_url='/docs',
        # openapi_tags=config.TAGS_METADATA
    )

    # Setup and register dependencies.
    apm_client = ApmClient(config)
    aiohttp_session = aiohttp.ClientSession(
        trust_env=True,
        headers={'x-sys-key': config.X_SYS_KEY},
    )
    chains = dependencies.ChainsConfig(
        api_key=config.PUBLIC_KEY,
        domain=config.PUBLIC_API_DOMAIN,
    )
    gas_service = dependencies.GasService(
        config=config,
        chains=chains,
    )
    providers = dependencies.ProvidersConfig()
    provider_registry = ProviderRegistry(
        ZeroXProviderV1(
            session=aiohttp_session,
            config=config,
            chains=chains,
            apm_client=apm_client,
        ),
        OneInchProviderV5(
            config=config,
            session=aiohttp_session,
            apm_client=apm_client,
        ),
        ParaSwapProviderV5(
            config=config,
            session=aiohttp_session,
            apm_client=apm_client,
        ),
        OpenOceanProviderV2(
            config=config,
            session=aiohttp_session,
            apm_client=apm_client,
        ),
        KyberSwapProviderV1(
            config=config,
            session=aiohttp_session,
            apm_client=apm_client,
            chains=chains,
        ),
        DebridgeDlnProviderV1(
            config=config,
            session=aiohttp_session,
            apm_client=apm_client,
            chains=chains,
        ),
    )
    crosschain_provider_registry = ProviderRegistry(
        DebridgeDlnProviderV1(
            config=config,
            session=aiohttp_session,
            apm_client=apm_client,
            chains=chains,
        ),
    )
    meta_aggregation_service = dependencies.MetaAggregationService(
        config=config,
        gas_service=gas_service,
        chains=chains,
        providers=providers,
        session=aiohttp_session,
        apm_client=apm_client,
        provider_registry=provider_registry,
        crosschain_provider_registry=crosschain_provider_registry,
    )
    limit_orders_service = dependencies.LimitOrdersService(
        config=config,
        session=aiohttp_session,
        apm_client=apm_client,
        provider_registry=provider_registry,
    )
    deps = dependencies.Dependencies(
        aiohttp_session=aiohttp_session,
        config=config,
        chains=chains,
        gas_service=gas_service,
        limit_orders_service=limit_orders_service,
        meta_aggregation_service=meta_aggregation_service,
        providers=providers,
    )
    deps.register(app)

    # Setup and register middlewares and routes.
    register_cors(app, config)
    register_gzip(app)
    register_route(app)
    register_route_logging(app)
    if config.APM_ENABLED:
        register_elastic_apm(app, ApmClient(config))

    # Common RFC 5741 Exceptions handling, https://tools.ietf.org/html/rfc5741#section-2
    @app.exception_handler(Exception)
    async def http_exception_handler(request: Request, exc):
        exception_dict = {
            "type": "Internal Server Error",
            "title": exc.__class__.__name__,
            "instance": f"{config.SERVER_HOST}{request.url.path}",
            "detail": f"{exc.__class__.__name__} at {str(exc)} when executing {request.method} request",
        }
        logger.error(
            "Exception when %s: %s",
            exception_dict["instance"],
            exception_dict["detail"],
        )
        return JSONResponse(exception_dict, status_code=500)

    @app.exception_handler(pydantic.error_wrappers.ValidationError)
    async def handle_validation_error(
        request: Request, exc: pydantic.error_wrappers.ValidationError
    ):  # pylint: disable=unused-argument
        """
        Handles validation errors.
        """
        return JSONResponse({"message": exc.errors()}, status_code=422)

    @app.exception_handler(BaseAggregationProviderError)
    async def handle_aggregation_provider_error(
        request: Request, exc: BaseAggregationProviderError
    ):
        return exc.to_http_exception()

    @app.exception_handler(AuthJWTException)
    def authjwt_exception_handler(request: Request, exc: AuthJWTException):
        return JSONResponse(
            status_code=exc.status_code, content={"detail": exc.message}
        )

    @app.on_event("startup")
    async def startup_event():
        await chains.set_chains()

    @app.on_event("shutdown")
    async def shutdown_event():
        await aiohttp_session.close()

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


def register_cors(app: FastAPI, config: Config):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=config.CORS_CREDENTIALS,
        allow_methods=config.CORS_METHODS,
        allow_headers=config.CORS_HEADERS,
    )


def register_gzip(app: FastAPI):
    app.add_middleware(GZipMiddleware, minimum_size=1000)


def register_route_logging(app: FastAPI):
    app.add_middleware(RouteLoggerMiddleware)


def register_elastic_apm(app: FastAPI, apm_client: ApmClient):
    app.add_middleware(ElasticAPM, client=apm_client.client)


def register_route(app: FastAPI):
    app.include_router(v1_rpc, prefix="/v1", tags=["RPC Requests"])
    app.include_router(gas_routes, prefix="/v1/gas", tags=["Gas"])
    app.include_router(info_route, prefix="/v1/info", tags=["Info"])
    app.include_router(swap_route, prefix="/v1/market", tags=["Swap"])
    app.include_router(crosschain_swap_route, prefix="/v1/crosschain", tags=["CrossChain Swap"])
    app.include_router(limit_orders, prefix="/v1/limit", tags=["Limit Orders"])
