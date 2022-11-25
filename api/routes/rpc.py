from aiohttp import ClientResponseError
from fastapi import APIRouter, Path, Depends, HTTPException
from fastapi.security import HTTPBearer
from pydantic import constr
from starlette.requests import Request

from utils.logger import get_logger

v1_rpc = APIRouter()
address_to_lower = constr(strip_whitespace=True, min_length=42, max_length=42, to_lower=True)
logger = get_logger(__name__)


@v1_rpc.post('/rpc/{network}', dependencies=[Depends(HTTPBearer())])
async def send_rpc(
        request: Request,
        network: str = Path(None, description="Network name"),
):
    from utils.httputils import CLIENT_SESSION
    # chain_id = get_chain_id_by_network(network)
    #
    # node = await find_most_synced_node_in_pool(logger=logger, chain_id=chain_id)
    node = ''
    if node is None:
        return {}
    try:
        async with CLIENT_SESSION.post(node, json=await request.json()) as response:
            return await response.json()
    except ClientResponseError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
