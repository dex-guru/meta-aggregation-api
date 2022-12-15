from typing import Optional, List

from fastapi import APIRouter, Path, Query

from meta_aggregation_api.services.limit_orders import \
    (get_limit_orders_by_wallet_address, get_limit_order_by_hash)
from meta_aggregation_api.utils.common import address_to_lower

limit_orders = APIRouter()


@limit_orders.get('/{chain_id}/address/{trader}')
@limit_orders.get('/{chain_id}/address/{trader}/', include_in_schema=False)
async def get_orders_by_trader(
        chain_id: int = Path(...),
        trader: address_to_lower = Path(..., description='The address of either the maker or the taker'),
        provider: Optional[str] = Query(None, description='e.g. 0x, 1inch'),
        maker_token: Optional[address_to_lower] = Query(None, description='The address of maker token'),
        taker_token: Optional[address_to_lower] = Query(None, description='The address of taker token'),
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
@limit_orders.get('/{chain_id}/events/{order_hash}/', include_in_schema=False)
async def get_limit_order_by_order_hash(
        chain_id: int = Path(...),
        order_hash: Optional[str] = Path(None, description='The hash of the order'),
        provider: Optional[str] = Query(None, description='e.g. 0x, 1inch'),
):
    response = await get_limit_order_by_hash(
        chain_id=chain_id,
        provider=provider,
        order_hash=order_hash,
    )
    return response
