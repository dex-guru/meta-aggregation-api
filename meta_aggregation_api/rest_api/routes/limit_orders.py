from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Path, Query
from fastapi.security import HTTPBearer
from fastapi_jwt_auth import AuthJWT

from meta_aggregation_api.models.meta_agg_models import LimitOrderPostData
from meta_aggregation_api.rest_api import dependencies
from meta_aggregation_api.utils.common import address_to_lower

limit_orders = APIRouter()


@limit_orders.get('/{chain_id}/address/{trader}')
@limit_orders.get('/{chain_id}/address/{trader}/', include_in_schema=False)
async def get_orders_by_trader(
    chain_id: int = Path(...),
    trader: address_to_lower = Path(
        ..., description='The address of either the maker or the taker'
    ),
    provider: str = Query(..., description='e.g. zero_x, one_inch'),
    maker_token: Optional[address_to_lower] = Query(
        None, description='The address of maker token'
    ),
    taker_token: Optional[address_to_lower] = Query(
        None, description='The address of taker token'
    ),
    statuses: Optional[List] = Query(None, description=''),
    service: dependencies.LimitOrdersService = Depends(
        dependencies.limit_orders_service
    ),
):
    response = await service.get_by_wallet_address(
        chain_id=chain_id,
        provider=provider,
        maker_token=maker_token,
        taker_token=taker_token,
        trader=trader,
        statuses=statuses,
    )
    return response


@limit_orders.get('/{chain_id}/events/{order_hash}')
@limit_orders.get('/{chain_id}/events/{order_hash}/', include_in_schema=False)
async def get_limit_order_by_order_hash(
    chain_id: int = Path(...),
    order_hash: Optional[str] = Path(None, description='The hash of the order'),
    provider: str = Query(..., description='e.g. zero_x, one_inch'),
    service: dependencies.LimitOrdersService = Depends(
        dependencies.limit_orders_service
    ),
):
    response = await service.get_by_hash(
        chain_id=chain_id,
        provider=provider,
        order_hash=order_hash,
    )
    return response


@limit_orders.post('/{chain_id}', dependencies=[Depends(HTTPBearer())])
@limit_orders.post(
    '/{chain_id}/', include_in_schema=False, dependencies=[Depends(HTTPBearer())]
)
async def make_limit_order(
    authorize: AuthJWT = Depends(),
    chain_id: int = Path(...),
    provider: Optional[str] = Query(..., description='e.g. zero_x, one_inch'),
    order_hash: str = Body(..., description='The hash of the order'),
    signature: str = Body(..., description='The signature of the order'),
    data: LimitOrderPostData = Body(..., description='The data of the order'),
    service: dependencies.LimitOrdersService = Depends(
        dependencies.limit_orders_service
    ),
):
    authorize.jwt_required()
    response = await service.post(
        chain_id=chain_id,
        provider=provider,
        order_hash=order_hash,
        signature=signature,
        data=data,
    )
    return response
