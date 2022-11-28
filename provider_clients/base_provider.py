import asyncio
from typing import Optional, Dict, List

from aiohttp import ClientSession, ServerDisconnectedError
from models.meta_aggregation_models import SwapPriceResponse, SwapQuoteResponse
from dexguru_utils.enums import NetworkChoices
from pydantic import ValidationError
from utils.logger import capture_exception

from utils.errors import ParseResponseError, BaseAggregationProviderError, ProviderTimeoutError


class BaseProvider:
    aiohttp_session: ClientSession
    _provider_name = 'base_provider'

    def __init__(self, aiohttp_session: Optional[ClientSession] = None):
        if not aiohttp_session:
            from utils.httputils import CLIENT_SESSION
            self.aiohttp_session = CLIENT_SESSION
        else:
            self.aiohttp_session = aiohttp_session

    async def get_swap_quote(
            self,
            buy_token: str,
            sell_token: str,
            sell_amount: int,
            network: Optional[NetworkChoices] = None,
            affiliate_address: Optional[str] = None,
            gas_price: Optional[int] = None,
            slippage_percentage: Optional[float] = None,
            taker_address: Optional[str] = None,
            fee_recipient: Optional[str] = None,
            buy_token_percentage_fee: Optional[float] = None
    ) -> SwapQuoteResponse:
        raise NotImplementedError

    async def get_swap_price(
            self,
            buy_token: str,
            sell_token: str,
            sell_amount: int,
            network: Optional[NetworkChoices] = None,
            affiliate_address: Optional[str] = None,
            gas_price: Optional[int] = None,
            slippage_percentage: Optional[float] = None,
            taker_address: Optional[str] = None,
            fee_recipient: Optional[str] = None,
            buy_token_percentage_fee: Optional[float] = None,
    ) -> SwapPriceResponse:
        raise NotImplementedError

    async def get_gas_prices(self, network: Optional[str] = None) -> dict:
        raise NotImplementedError

    async def get_orders_by_trader(
            self,
            trader: str,
            maker_token: str,
            taker_token: str,
            network: Optional[str] = None,
            statuses: Optional[List[str]] = None,
    ) -> List[Dict]:
        raise NotImplementedError

    async def get_order_by_hash(
            self,
            network: NetworkChoices,
            order_hash: str,
    ) -> Dict:
        raise NotImplementedError

    def handle_exception(self, exception: Exception, logger, **kwargs) -> BaseAggregationProviderError:
        capture_exception()
        if isinstance(exception, KeyError) or isinstance(exception, ValidationError):
            exc = ParseResponseError(self._provider_name, str(exception), **kwargs)
            logger.error(*exc.to_log_args(), extra=exc.to_dict())
            return exc
        if isinstance(exception, ServerDisconnectedError) or isinstance(exception, asyncio.TimeoutError):
            exc = ProviderTimeoutError(self._provider_name, str(exception), **kwargs)
            logger.error(*exc.to_log_args(), extra=exc.to_dict())
            return exc
