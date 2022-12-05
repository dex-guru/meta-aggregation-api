from fastapi import Path, HTTPException
from fastapi.routing import APIRouter

from service.gas_service import get_gas_prices

gas_routes = APIRouter()


@gas_routes.get('/{chain_id}')
async def get_prices(chain_id: int = Path(None, description='Network')) -> dict:
    try:
        res: dict = await get_gas_prices(chain_id)
    except Exception as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    else:
        return res
