from fastapi import Path, HTTPException
from fastapi.routing import APIRouter

from models.gas_models import GasResponse
from service.gas_service import get_gas_prices

gas_routes = APIRouter()


@gas_routes.get('/{chain_id}', response_model=GasResponse)
async def get_prices(chain_id: int = Path(None, description='Network')) -> GasResponse:
    try:
        res: GasResponse = await get_gas_prices(chain_id)
    except Exception as e:
        raise HTTPException(detail=str(e), status_code=500)
    else:
        return res
