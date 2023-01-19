from typing import Optional, List

from aiocache import cached
from fastapi import APIRouter, Path, Query, Body, Depends
from fastapi.security import HTTPBearer
from fastapi_jwt_auth import AuthJWT

from meta_aggregation_api.models.meta_agg_models import LimitOrderPostData
from meta_aggregation_api.services.limit_orders import \
    (get_limit_orders_by_wallet_address, get_limit_order_by_hash, post_limit_order)
from meta_aggregation_api.utils.cache import get_cache_config
from meta_aggregation_api.utils.common import address_to_lower

LIMIT_ORDERS_CACHE_TTL_SEC = 10
limit_orders = APIRouter()


@limit_orders.get('/{chain_id}/address/{trader}')
@limit_orders.get('/{chain_id}/address/{trader}/', include_in_schema=False)
@cached(ttl=LIMIT_ORDERS_CACHE_TTL_SEC, **get_cache_config())
async def get_orders_by_trader(
    chain_id: int = Path(...),
    trader: address_to_lower = Path(...,
                                    description='The address of either the maker or the taker'),
    provider: str = Query(..., description='e.g. zero_x, one_inch'),
    maker_token: Optional[address_to_lower] = Query(None,
                                                    description='The address of maker token'),
    taker_token: Optional[address_to_lower] = Query(None,
                                                    description='The address of taker token'),
    statuses: Optional[List] = Query(None, description=''),
):
    response = await get_limit_orders_by_wallet_address(
        chain_id=chain_id,
        provider=provider,
        maker_token=maker_token,
        taker_token=taker_token,
        trader=trader,
        statuses=statuses,
    )
    return response


@limit_orders.get('/{chain_id}/events/{order_hash}')
@limit_orders.get('/{chain_id}/events/{order_hash}/',
                  include_in_schema=False)
@cached(ttl=LIMIT_ORDERS_CACHE_TTL_SEC, **get_cache_config())
async def get_limit_order_by_order_hash(
    chain_id: int = Path(...),
    order_hash: Optional[str] = Path(None, description='The hash of the order'),
    provider: str = Query(..., description='e.g. zero_x, one_inch'),
):
    response = await get_limit_order_by_hash(
        chain_id=chain_id,
        provider=provider,
        order_hash=order_hash,
    )
    return response


@limit_orders.post('/{chain_id}', dependencies=[Depends(HTTPBearer())])
@limit_orders.post('/{chain_id}/', include_in_schema=False,
                   dependencies=[Depends(HTTPBearer())])
async def make_limit_order(
    authorize: AuthJWT = Depends(),
    chain_id: int = Path(...),
    provider: Optional[str] = Query(..., description='e.g. zero_x, one_inch'),
    order_hash: str = Body(..., description='The hash of the order'),
    signature: str = Body(..., description='The signature of the order'),
    data: LimitOrderPostData = Body(..., description='The data of the order'),
):
    authorize.jwt_required()
    response = await post_limit_order(
        chain_id=chain_id,
        provider=provider,
        order_hash=order_hash,
        signature=signature,
        data=data,
    )
    return response
