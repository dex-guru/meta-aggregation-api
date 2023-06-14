import ssl

import aiohttp
from aiocache import cached
from aiohttp import ClientResponseError
from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.security import HTTPBearer
from fastapi_jwt_auth import AuthJWT
from starlette.requests import Request

from meta_aggregation_api.rest_api import dependencies
from meta_aggregation_api.rest_api.dependencies import aiohttp_session
from meta_aggregation_api.utils.cache import get_cache_config
from meta_aggregation_api.utils.common import get_web3_url
from meta_aggregation_api.utils.logger import get_logger

v1_rpc = APIRouter()
logger = get_logger(__name__)


@v1_rpc.post('/rpc/{chain_id}', dependencies=[Depends(HTTPBearer())])
async def send_rpc(
    request: Request,
    authorize: AuthJWT = Depends(),
    chain_id: int = Path(..., description="Chain ID"),
    session: aiohttp.ClientSession = Depends(aiohttp_session),
    config: dependencies.Config = Depends(dependencies.config),
):
    """
    The send_rpc function is an endpoint that makes an HTTP request to the node
    that is currently synced with the most other nodes. It takes in a JSON-RPC 2.0 compliant
    request and returns a JSON-RPC 2.0 compliant response.
    """

    authorize.jwt_required()
    node = get_web3_url(chain_id, config)
    body = await request.json()
    if body.get('method') == 'eth_chainId':
        return {'jsonrpc': '2.0', 'id': body['id'], 'result': hex(chain_id)}
    if body.get('method') == 'net_version':
        return {'jsonrpc': '2.0', 'id': body['id'], 'result': str(chain_id)}

    @cached(ttl=5, **get_cache_config(config))
    async def make_request(node_, body_):
        try:
            async with session.post(
                node_, proxy=None, json=body_, ssl=ssl.SSLContext()
            ) as response:
                return await response.json()
        except ClientResponseError as e:
            raise HTTPException(status_code=e.status, detail=e.message)

    return await make_request(node, body)
