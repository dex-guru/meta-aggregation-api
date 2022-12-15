from fastapi import Path
from fastapi.routing import APIRouter

from meta_aggregation_api.models.gas_models import GasResponse
from meta_aggregation_api.services.gas_service import get_gas_prices

gas_routes = APIRouter()


@gas_routes.get('/{chain_id}', response_model=GasResponse)
async def get_prices(chain_id: int = Path(..., description='Chain ID')) -> GasResponse:
    """
    Returns the gas prices for a given chain.
    Returned object has not null eip1559 field for chains that support it.
    """
    return await get_gas_prices(chain_id)
