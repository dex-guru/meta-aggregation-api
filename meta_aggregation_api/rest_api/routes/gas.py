from aiocache import cached
from fastapi import Path
from fastapi.routing import APIRouter

from meta_aggregation_api.models.gas_models import GasResponse
from meta_aggregation_api.services.gas_service import get_gas_prices
from meta_aggregation_api.utils.cache import get_cache_config

GAS_CACHE_TTL_SEC = 5
gas_routes = APIRouter()


@gas_routes.get('/{chain_id}', response_model=GasResponse)
@gas_routes.get('/{chain_id}/', include_in_schema=False)
@cached(ttl=GAS_CACHE_TTL_SEC, **get_cache_config())
async def get_prices(
    chain_id: int = Path(..., description='Chain ID'),
) -> GasResponse:
    """
    Returns the gas prices for a given chain.
    Returned object has not null eip1559 field for chains that support it.
    """
    return await get_gas_prices(chain_id)
