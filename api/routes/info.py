from fastapi import APIRouter, Path, HTTPException
from starlette.requests import Request

from models.chain import ProvidersConfigModel

info_route = APIRouter()


@info_route.get('/')
@info_route.get('', include_in_schema=False)
async def get_all_info(
        request: Request,
):
    """
    Returns information about the providers on all supported chains.
    This includes name, spender_address and display_name.
    """
    return request.app.providers


@info_route.get('/{chain_id}', response_model=ProvidersConfigModel,
                responses={404: {"description": "Chain ID not found"}})
@info_route.get('/{chain_id}/', include_in_schema=False, response_model=ProvidersConfigModel)
async def get_info(
        request: Request,
        chain_id: int = Path(..., description='Chain ID'),
) -> ProvidersConfigModel:
    """Returns information about the providers for a given chain ID."""
    info = request.app.providers.get(str(chain_id))
    if not info:
        raise HTTPException(status_code=404, detail='Chain ID not found')
    return info
