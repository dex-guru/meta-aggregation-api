from aiohttp import ClientResponseError
from fastapi import APIRouter, Path, Depends, HTTPException
from fastapi.security import HTTPBearer
from pydantic import constr
from starlette.requests import Request

from config import chains, config
from utils.logger import get_logger

v1_rpc = APIRouter()
address_to_lower = constr(strip_whitespace=True, min_length=42, max_length=42, to_lower=True)
logger = get_logger(__name__)


@v1_rpc.post('/rpc/{network}', dependencies=[Depends(HTTPBearer())])
async def send_rpc(
        request: Request,
        network: str = Path(None, description="Network name"),
):
    # TODO: Add rpc endpoint description
    from utils.httputils import CLIENT_SESSION
    # TODO: don't forget to remove
    chain_id = chains[network].chain_id
    #
    # node = await find_most_synced_node_in_pool(logger=logger, chain_id=chain_id)
    # TODO: app.config?
    node = config.WEB3_URL
    if node is None:
        return {}
    try:
        async with CLIENT_SESSION.post(node, json=await request.json()) as response:
            return await response.json()
    except ClientResponseError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
