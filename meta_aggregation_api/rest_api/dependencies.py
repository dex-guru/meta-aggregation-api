import aiohttp
import fastapi
from pydantic import BaseModel

from meta_aggregation_api.config import Config
from meta_aggregation_api.config.providers import ProvidersConfig
from meta_aggregation_api.services.chains import ChainsConfig
from meta_aggregation_api.services.gas_service import GasService
from meta_aggregation_api.services.limit_orders import LimitOrdersService
from meta_aggregation_api.services.meta_aggregation_service import (
    MetaAggregationService,
)


class Dependencies(BaseModel):
    """
    Holds the dependencies that should exist for the lifetime of the application.
    """

    aiohttp_session: aiohttp.ClientSession
    config: Config
    chains: ChainsConfig
    gas_service: GasService
    limit_orders_service: LimitOrdersService
    meta_aggregation_service: MetaAggregationService
    providers: ProvidersConfig

    class Config:
        arbitrary_types_allowed = True
        extra = "forbid"
        allow_mutation = False

    def register(self, app: fastapi.FastAPI):
        """
        Registers itself in the application.
        """
        app.state.dependencies = self


def _get(request: fastapi.Request) -> Dependencies:
    return request.app.state.dependencies


def aiohttp_session(request: fastapi.Request) -> aiohttp.ClientSession:
    return _get(request).aiohttp_session


def config(request: fastapi.Request) -> Config:
    return _get(request).config


def chains(request: fastapi.Request) -> ChainsConfig:
    return _get(request).chains


def gas_service(request: fastapi.Request) -> GasService:
    return _get(request).gas_service


def limit_orders_service(request: fastapi.Request) -> LimitOrdersService:
    return _get(request).limit_orders_service


def meta_aggregation_service(request: fastapi.Request) -> MetaAggregationService:
    return _get(request).meta_aggregation_service


def providers(request: fastapi.Request) -> ProvidersConfig:
    return _get(request).providers
