from fastapi import Depends, Path
from fastapi.routing import APIRouter
from fastapi.security import HTTPBearer
from fastapi_jwt_auth import AuthJWT

from meta_aggregation_api.models.gas_models import GasResponse
from meta_aggregation_api.rest_api import dependencies

gas_routes = APIRouter()


@gas_routes.get(
    '/{chain_id}', response_model=GasResponse, dependencies=[Depends(HTTPBearer())]
)
@gas_routes.get(
    '/{chain_id}/', include_in_schema=False, dependencies=[Depends(HTTPBearer())]
)
@gas_routes.get('/{chain_id}', response_model=GasResponse)
@gas_routes.get('/{chain_id}/', include_in_schema=False)
async def get_prices(
    authorize: AuthJWT = Depends(),
    chain_id: int = Path(..., description='Chain ID'),
    gas_service: dependencies.GasService = Depends(dependencies.gas_service),
) -> GasResponse:
    """
    Returns the gas prices for a given chain.
    Returned object has not null eip1559 field for chains that support it.
    """
    authorize.jwt_required()
    return await gas_service.get_gas_prices(chain_id)
