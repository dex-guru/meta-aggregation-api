from aiohttp import ClientResponseError
from fastapi import APIRouter, Path, Depends, HTTPException
from fastapi.security import HTTPBearer
from pydantic import constr
from starlette.requests import Request

from utils.common import get_web3_url
from utils.logger import get_logger

v1_rpc = APIRouter()
address_to_lower = constr(strip_whitespace=True, min_length=42, max_length=42, to_lower=True)
logger = get_logger(__name__)


@v1_rpc.post('/rpc/{chain_id}', dependencies=[Depends(HTTPBearer())])
async def send_rpc(
        request: Request,
        chain_id: int = Path(..., description="Chain ID"),
):
    """
    The send_rpc function is an endpoint that makes an HTTP request to the node
    that is currently synced with the most other nodes. It takes in a JSON-RPC 2.0 compliant
    request and returns a JSON-RPC 2.0 compliant response.
    """
    from utils.httputils import CLIENT_SESSION
    node = get_web3_url(chain_id)
    try:
        async with CLIENT_SESSION.post(node, json=await request.json()) as response:
            return await response.json()
    except ClientResponseError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
