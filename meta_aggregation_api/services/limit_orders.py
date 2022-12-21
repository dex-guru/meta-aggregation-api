from typing import Optional, List, Dict

from meta_aggregation_api.models.meta_agg_models import LimitOrderPostData
from meta_aggregation_api.providers import all_providers
from meta_aggregation_api.utils.errors import ProviderNotFound
from meta_aggregation_api.utils.logger import get_logger

logger = get_logger(__name__)


async def get_limit_orders_by_wallet_address(
    chain_id: int,
    trader: str,
    provider: Optional[str] = None,
    maker_token: Optional[str] = None,
    taker_token: Optional[str] = None,
    statuses: Optional[List] = None,
) -> List[Dict]:
    provider_class = all_providers.get(provider)
    if not provider_class:
        raise ProviderNotFound(provider)
    provider_instance = provider_class()
    logger.info(
        f'Getting limit orders by wallet address: {trader}',
        extra={'provider': provider.__class__.__name__,
               'trader': trader, 'maker_token': maker_token,
               'taker_token': taker_token}
    )
    res = await provider_instance.get_orders_by_trader(
        chain_id=chain_id,
        trader=trader,
        maker_token=maker_token,
        taker_token=taker_token,
        statuses=statuses,
    )
    logger.info(
        f'got {len(res)} limit orders by wallet address: {trader}',
        extra={'wallet_address': trader, 'limit_orders_count': len(res),
               'provider': provider.__class__.__name__},
    )
    return res


async def get_limit_order_by_hash(
    chain_id: int,
    order_hash: str,
    provider: Optional[str],
):
    provider_class = all_providers.get(provider)
    if not provider_class:
        raise ProviderNotFound(provider)
    provider_instance = provider_class()
    logger.info(f'Getting limit order by hash: {order_hash}',
                extra={'provider': provider.__class__.__name__,
                       'order_hash': order_hash})
    res = await provider_instance.get_order_by_hash(
        chain_id=chain_id,
        order_hash=order_hash,
    )
    return res


async def post_limit_order(
    chain_id: int,
    provider: Optional[str],
    order_hash: str,
    signature: str,
    data: LimitOrderPostData,
):
    provider_class = all_providers.get(provider)
    if not provider_class:
        raise ProviderNotFound(provider)
    provider_instance = provider_class()
    logger.info(
        f'Posting limit order: {order_hash}',
        extra={'provider': provider.__class__.__name__,
               'order_hash': order_hash}
    )
    response = await provider_instance.post_limit_order(
        chain_id=chain_id,
        order_hash=order_hash,
        signature=signature,
        data=data.dict(),
    )
    return response
