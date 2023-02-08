from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path

from meta_aggregation_api.models.chain import (
    AllProvidersConfigModel,
    ProvidersConfigModel,
)
from meta_aggregation_api.rest_api import dependencies

info_route = APIRouter()


@info_route.get('/', response_model=List[AllProvidersConfigModel])
@info_route.get('', include_in_schema=False)
async def get_all_info(
    providers: dependencies.ProvidersConfig = Depends(dependencies.providers),
):
    """
    Returns information about the providers on all supported chains.
    This includes name, spender_address and display_name.
    """
    info = providers.get_all_providers()
    return info


@info_route.get(
    '/{chain_id}',
    response_model=ProvidersConfigModel,
    response_model_exclude={'chain_id'},
    responses={404: {"description": "Chain ID not found"}},
)
@info_route.get(
    '/{chain_id}/',
    include_in_schema=False,
    response_model=ProvidersConfigModel,
    response_model_exclude={'chain_id'},
)
async def get_info(
    chain_id: int = Path(..., description='Chain ID'),
    providers: dependencies.ProvidersConfig = Depends(dependencies.providers),
) -> ProvidersConfigModel:
    """Returns information about the providers for a given chain ID."""
    try:
        info = providers.get_providers_on_chain(chain_id)
    except ValueError:
        raise HTTPException(status_code=404, detail='Chain ID not found')
    else:
        return info
