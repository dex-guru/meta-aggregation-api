import asyncio
from abc import abstractmethod
from typing import Optional

from aiohttp import ClientSession, ServerDisconnectedError
from pydantic import ValidationError

from models.meta_agg_models import SwapQuoteResponse, ProviderPriceResponse
from utils.errors import ParseResponseError, BaseAggregationProviderError, ProviderTimeoutError
from utils.logger import capture_exception


class BaseProvider:
    aiohttp_session: ClientSession
    PROVIDER_NAME = 'base_provider'
    REQUEST_TIMEOUT = 5

    def __init__(self, aiohttp_session: Optional[ClientSession] = None):
        if not aiohttp_session:
            from utils.httputils import CLIENT_SESSION
            self.aiohttp_session = CLIENT_SESSION
        else:
            self.aiohttp_session = aiohttp_session

    @abstractmethod
    async def get_swap_quote(
            self,
            buy_token: str,
            sell_token: str,
            sell_amount: int,
            chain_id: int,
            taker_address: str,
            gas_price: Optional[int] = None,
            slippage_percentage: Optional[float] = None,
            fee_recipient: Optional[str] = None,
            buy_token_percentage_fee: Optional[float] = None
    ) -> SwapQuoteResponse:
        """
        The get_swap_quote function is used to get the data for a swap from the provider.
        Args:
            self: Access the class attributes
            buy_token:str: Token is being buy
            sell_token:str: Token is being sold
            sell_amount:int: Amount of sell_token to sell
            chain_id:int: Specify the chain on which the transaction will be executed
            taker_address:str: Address who makes the transaction and will receive tokens
            gas_price:Optional[int]=None: Specify the gas price for the transaction
            slippage_percentage:Optional[float]=None: Specify the percentage of slippage to apply to the quote
            fee_recipient:Optional[str]=None: Address who will receive the fee
            buy_token_percentage_fee:Optional[float]=None: Percentage of the buy_token fee that will be paid to the fee_recipient

        Returns:
            A SwapQuoteResponse object with the data for the swap.
        """

    @abstractmethod
    async def get_swap_price(
            self,
            buy_token: str,
            sell_token: str,
            sell_amount: int,
            chain_id: Optional[int] = None,
            gas_price: Optional[int] = None,
            slippage_percentage: Optional[float] = None,
            taker_address: Optional[str] = None,
            fee_recipient: Optional[str] = None,
            buy_token_percentage_fee: Optional[float] = None,
    ) -> ProviderPriceResponse:
        ...

    def handle_exception(self, exception: Exception, logger, **kwargs) -> BaseAggregationProviderError:
        capture_exception()
        if isinstance(exception, KeyError) or isinstance(exception, ValidationError):
            exc = ParseResponseError(self.PROVIDER_NAME, str(exception), **kwargs)
            logger.error(*exc.to_log_args(), extra=exc.to_dict())
            return exc
        if isinstance(exception, ServerDisconnectedError) or isinstance(exception, asyncio.TimeoutError):
            exc = ProviderTimeoutError(self.PROVIDER_NAME, str(exception), **kwargs)
            logger.error(*exc.to_log_args(), extra=exc.to_dict())
            return exc
