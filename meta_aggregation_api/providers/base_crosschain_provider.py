import asyncio
from abc import ABC, abstractmethod
from typing import Optional

import aiohttp
from pydantic import ValidationError

from meta_aggregation_api.clients.apm_client import ApmClient
from meta_aggregation_api.config import Config
from meta_aggregation_api.models.meta_agg_models import (
    ProviderPriceResponse,
    ProviderQuoteResponse,
)
from meta_aggregation_api.utils.errors import (
    BaseAggregationProviderError,
    ParseResponseError,
    ProviderTimeoutError,
)
from meta_aggregation_api.utils.logger import capture_exception


class CrossChainProvider(ABC):
    PROVIDER_NAME = 'base_crosschain_provider'
    REQUEST_TIMEOUT = 7

    def __init__(
        self,
        session: aiohttp.ClientSession,
        config: Config,
        apm_client: ApmClient,
        **_,
    ):
        self.apm_client = apm_client
        self.aiohttp_session = session
        self.config = config

    @abstractmethod
    def is_require_gas_price(self) -> bool:
        pass


    @abstractmethod
    async def get_swap_quote(
        self,
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        chain_id_from: int,
        chain_id_to: int,
        taker_address: str,
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None,
    ) -> ProviderQuoteResponse:
        """
        The get_swap_quote function is used to get the data for a swap from the provider.
        Args:
            self: Access the class attributes
            buy_token:str: Token is being buy
            sell_token:str: Token is being sold
            sell_amount:int: Amount of sell_token to sell
            chain_id_from:int: Specify the chain on which the transaction will be executed, a chain where the cross-chain swap will start
            chain_id_to:int: chain where the cross-chain swap will finish
            taker_address:str: Address who makes the transaction and will receive tokens
            gas_price:Optional[int]=None: Specify the gas price for the transaction
            slippage_percentage:Optional[float]=None: Specify the percentage of slippage to apply to the quote
            fee_recipient:Optional[str]=None: Address who will receive the fee
            buy_token_percentage_fee:Optional[float]=None: Percentage of the buy_token fee that will be paid to the fee_recipient

        Returns:
            A ProviderQuoteResponse object with the data for the swap. Check return type for more info.
        """

    @abstractmethod
    async def get_swap_price(
        self,
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        chain_id_from: int,
        chain_id_to: int,
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = None,
        taker_address: Optional[str] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None,
    ) -> ProviderPriceResponse:
        """
        The get_swap_price function is used to find the best price for a swap from the provider.
        It doesn't require the taker_address to be specified.
        Args:
            self: Access the class attributes
            buy_token:str: Token is being buy
            sell_token:str: Token is being sold
            sell_amount:int: Amount of sell_token to sell
            chain_id_from:int: Specify the chain on which the transaction will be executed, a chain where the cross-chain swap will start
            chain_id_to:int: chain where the cross-chain swap will finish
            gas_price:Optional[int]=None: Specify the gas price for the transaction
            slippage_percentage:Optional[float]=None: Specify the percentage of slippage to apply to the quote
            taker_address:Optional[str]=None: Address who makes the transaction and will receive tokens
            fee_recipient:Optional[str]=None: Address who will receive the fee
            buy_token_percentage_fee:Optional[float]=None: Percentage of the buy_token fee that will be paid to the fee_recipient

        Returns:
            A ProviderPriceResponse object with the price for the swap. Check return type for more info.
        """

    def handle_exception(
        self, exception: Exception, **kwargs
    ) -> BaseAggregationProviderError:
        capture_exception(self.apm_client)
        if isinstance(exception, (KeyError, ValidationError)):
            exc = ParseResponseError(self.PROVIDER_NAME, str(exception), **kwargs)
            return exc
        if isinstance(
            exception, (aiohttp.ServerDisconnectedError, asyncio.TimeoutError)
        ):
            exc = ProviderTimeoutError(self.PROVIDER_NAME, str(exception), **kwargs)
            return exc
