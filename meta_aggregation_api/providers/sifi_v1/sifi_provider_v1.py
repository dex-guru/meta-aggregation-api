import asyncio
import ssl
from pathlib import Path
from typing import Optional, Union
import ujson
from aiocache import cached
from aiohttp import ClientResponseError, ServerDisconnectedError
from pydantic import ValidationError
from meta_aggregation_api.models.meta_agg_models import (
    ProviderPriceResponse,
    ProviderQuoteResponse,
)
from meta_aggregation_api.providers.paraswap_v5 import ParaSwapProviderV5
from meta_aggregation_api.models.provider_response_models import SwapSources
from meta_aggregation_api.providers.base_provider import BaseProvider
from meta_aggregation_api.utils.cache import get_cache_config
from meta_aggregation_api.utils.errors import (
    AggregationProviderError,
    AllowanceError,
    BaseAggregationProviderError,
    EstimationError,
    PriceError,
    TokensError,
    UserBalanceError,
    ValidationFailedError,
)
from meta_aggregation_api.utils.logger import get_logger

logger = get_logger(__name__)

ERROR_CODE_TO_CLASS = {
    'INSUFFICIENT_BALANCE': UserBalanceError,
    'TOKEN_NOT_FOUND': TokensError,
    'ESTIMATE_GAS_FAILED': EstimationError,
    'INVALID_RECIPIENT': ValidationFailedError,
    'INSUFFICIENT_ALLOWANCE': AllowanceError,
    'PATH_NOT_FOUND': PriceError,
    'SWAP_TO_ADDRESS_NOT_SUPPORTED': AggregationProviderError,
    'ENCODE_SWAP_TX_FAILED': AggregationProviderError,
    'BAD_REQUEST': ValidationFailedError,
    'PERMIT_NOT_SUPPORTED': ValidationFailedError,
}

def from_hex(value: str) -> str:
    return str(int(value, 16))

class SifiProviderV1(BaseProvider):
    """
    Trading Provider for Sifi v1 dex aggregator
    Docs: https://docs.sifi.org
    """

    with open(Path(__file__).parent / 'config.json') as f:
        PROVIDER_NAME = ujson.load(f)['name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.get_swap_price = cached(
            ttl=30, **get_cache_config(self.config), noself=True
        )(self.get_swap_price)

    async def request(self, method: str, path: str, *args, **kwargs):
        request_function = getattr(self.aiohttp_session, method.lower())
        url = f'https://api.sifi.org/v1/{path}'
        async with request_function(
            url, *args, timeout=self.REQUEST_TIMEOUT, **kwargs, ssl=ssl.SSLContext()
        ) as response:
            logger.debug("Request '%s' to '%s'", method, url)
            data = await response.text()
            try:
                response.raise_for_status()
            except ClientResponseError as e:
                # Fix bug with HTTP status code 0.
                status = 500 if e.status not in range(100, 600) else e.status
                raise ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=status,
                    message=data,
                    headers=response.headers,
                )
        return ujson.loads(data)

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
    ):
        params = {
            'fromChain': chain_id,
            'fromToken': sell_token,
            'toToken': buy_token,
            'fromAmount': sell_amount,
            'disablePermit': 1,
        }

        try:
            quote = await self.request(method='get', path='quote', params=params)
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ServerDisconnectedError,
            Exception,
        ) as e:
            e = self.handle_exception(
                e, method='get_swap_price', params=params, chain_id=chain_id
            )
            raise e
        response = self._convert_response_from_swap_price(quote)
        response.gas_price = gas_price or 0
        if sell_token.lower() == self.config.NATIVE_TOKEN_ADDRESS:
            response.value = str(sell_amount)
        return response

    async def get_swap_quote(
        self,
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        taker_address: str,
        chain_id: Optional[int] = None,
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None,
        ignore_checks: bool = False,
    ) -> Optional[ProviderQuoteResponse]:
        quote_params = {
            'fromChain': chain_id,
            'fromToken': sell_token,
            'toToken': buy_token,
            'fromAmount': sell_amount,
            'disablePermit': 1,
        }
        try:
            quote = await self.request(method='get', path='quote', params=quote_params)
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ServerDisconnectedError,
        ) as e:
            e = self.handle_exception(
                e, method='get_swap_quote', params=quote_params, chain_id=chain_id
            )
            raise e

        swap_body = {
            'quote': quote,
            'fromAddress': taker_address,
        }

        if buy_token_percentage_fee:
            swap_body['feeBps'] = int(
                buy_token_percentage_fee * 10000
            )  # 100% -> 10000

        if slippage_percentage:
            swap_body['slippage'] = int(slippage_percentage * 10000)  # 100% -> 10000

        if fee_recipient:
            swap_body['partner'] = fee_recipient

        try:
            swap = await self.request(
                method='post',
                path='swap',
                json=swap_body,
            )
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ServerDisconnectedError,
        ) as e:
            e = self.handle_exception(
                e, swap_body=swap_body, chain_id=chain_id
            )
            raise e

        converted = self._convert_response_from_swap_quote(swap, quote)

        if gas_price:
            converted.gas_price = str(gas_price)

        return converted

    def _get_price_from_quote(self, quote: dict) -> float:
        ratio = float(quote['toAmount']) / float(quote['fromAmount'])
        exp = quote['fromToken']['decimals'] - quote['toToken']['decimals']
        return ratio * 10 ** exp

    def _convert_response_from_swap_quote(
        self,
        swap: dict,
        quote: dict,
        **kwargs,
    ) -> Optional[ProviderQuoteResponse]:
        price = self._get_price_from_quote(quote)
        tx = swap['tx']

        try:
            return ProviderQuoteResponse(
                sources=self.convert_sources_for_meta_aggregation(quote),
                buy_amount=str(quote['toAmount']),
                gas=from_hex(tx.get('gasLimit', '0')),
                sell_amount=quote['toAmount'],
                to=tx['to'],
                data=tx['data'],
                gas_price=swap.get('gasPrice', '0'),
                value=from_hex(tx.get('value', '0')),
                price=str(price),
            )
        except (KeyError, ValidationError) as e:
            e = self.handle_exception(
                e,
                response=swap,
                method='_convert_response_from_swap_quote',
                price_response=price,
                **kwargs,
            )
            raise e

    def _convert_response_from_swap_price(
        self, quote: dict
    ) -> Optional[ProviderPriceResponse]:
        sources = self.convert_sources_for_meta_aggregation(quote)
        try:
            prepared_response = ProviderPriceResponse(
                provider=self.PROVIDER_NAME,
                sources=sources,
                buy_amount=str(quote['toAmount']),
                gas=quote['estimatedGas'],
                sell_amount=quote['fromAmount'],
                gas_price='0',
                value='0',
                price=str(self._get_price_from_quote(quote)),
            )
        except (KeyError, ValidationError) as e:
            e = self.handle_exception(
                e, response=quote, method='_convert_response_from_swap_price'
            )
            raise e
        else:
            return prepared_response

    @staticmethod
    def _get_swap_sources_from_element(
        element: dict
    ) -> list[SwapSources]:
        """
        Sifi supports unlimited series of swaps with nested splits. For example, the swap:

                                  ___ Curve ____ Uniswap V3_
                           60%  /                            \
        Uniswap V3 (100%) ------                              ----- Uniswap V3 (100%)
                           40%   \___ SushiSwap ____________ /

        Will be returned as the proportions:

        * Uniswap V3: 33.3% + 10% + 33.3% = 76.6%
        * Curve: 10%
        * SushiSwap 13.33%

        Which is the proportion of the total swap volume going through the pools of each venue.
        """
        sources = []

        element_share_pct = float(element['shareBps']) / 100
        element_counted_children = 0

        for action in element['actions']:
            if action['type'] == 'split':
                element_counted_children += 1

                for part_element in action['parts']:
                    sources.extend(SifiProviderV1._get_swap_sources_from_element(part_element))
            else:
                exchange = action.get('exchange')

                if exchange:
                    element_counted_children += 1
                    sources.append(SwapSources(name=exchange, proportion=100.0))

        grouped_sources = []

        for source in sources:
            source.proportion  = (source.proportion / element_counted_children) * (element_share_pct / 100)
            existing = next((s for s in grouped_sources if s.name == source.name), None)

            if existing:
                existing.proportion += source.proportion
            else:
                grouped_sources.append(source)

        return grouped_sources

    @staticmethod
    def convert_sources_for_meta_aggregation(
        quote: Optional[Union[dict, list[dict]]],
    ) -> Optional[list[SwapSources]]:
        if quote['source']['name'] == 'paraswap':
            ParaSwapProviderV5.convert_sources_for_meta_aggregation(quote['source']['quote']['bestRoute'])

        if quote['source']['name'] == 'sifi':
            return SifiProviderV1._get_swap_sources_from_element(quote['source']['quote']['element'])

        return []

    def handle_exception(
        self,
        exception: Union[ClientResponseError, KeyError, ValidationError],
        **kwargs,
    ) -> BaseAggregationProviderError:
        exc = super().handle_exception(exception, **kwargs)
        if exc:
            logger.error(*exc.to_log_args(), extra=exc.to_dict())
            return exc
        msg = exception.message
        try:
            details = ujson.loads(msg)
            code = details['code']
            msg = details['message']
        except (KeyError, ValueError):
            code = None

        error_class = ERROR_CODE_TO_CLASS.get(code, AggregationProviderError)

        exc = error_class(
            self.PROVIDER_NAME,
            msg,
            url=str(exception.request_info.url),
            **kwargs,
        )

        logger.warning(*exc.to_log_args(), extra=exc.to_dict())
        return exc
