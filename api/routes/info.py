from fastapi import APIRouter, Path, HTTPException

from config.providers import providers
from models.chain import ProvidersConfigModel

info_route = APIRouter()


@info_route.get('/')
@info_route.get('', include_in_schema=False)
async def get_all_info():
    # TODO: why not app.config?
    return providers


@info_route.get('/{chain_id}', response_model=ProvidersConfigModel)
@info_route.get('/{chain_id}/', include_in_schema=False, response_model=ProvidersConfigModel)
async def get_info(
        chain_id: int = Path(None, description='Chain ID'),
) -> ProvidersConfigModel:
    # TODO: why not app.config?
    info = providers.get(str(chain_id))
    if not info:
        raise HTTPException(status_code=404, detail='Chain ID not found.')
    return info
