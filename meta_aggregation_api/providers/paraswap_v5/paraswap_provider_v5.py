import asyncio
import re
import ssl
from decimal import Decimal
from itertools import chain
from pathlib import Path
from typing import Optional, Union

import ujson
import yarl
from aiocache import cached
from aiohttp import ClientResponseError, ServerDisconnectedError
from pydantic import ValidationError

from meta_aggregation_api.models.meta_agg_models import (
    ProviderPriceResponse,
    ProviderQuoteResponse,
)
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
from meta_aggregation_api.utils.logger import LogArgs, get_logger

logger = get_logger(__name__)

PARASWAP_ERRORS = {
    # ---- price errors
    'Invalid tokens': TokensError,
    'Token not found': TokensError,
    'Price Timeout': PriceError,
    'computePrice Error': PriceError,
    'Bad USD price': PriceError,
    'ERROR_GETTING_PRICES': PriceError,
    # ---- price_response errors
    'Unable to check price impact': PriceError,
    r'not enough \w+ balance': UserBalanceError,
    r'not enough \w+ allowance': AllowanceError,
    'It seems like your wallet doesn\'t contain enough': UserBalanceError,
    'Network Mismatch': ValidationFailedError,
    'Missing srcAmount': ValidationFailedError,
    'Missing destAmount': ValidationFailedError,
    'Cannot specify both slippage and destAmount': ValidationFailedError,
    'Missing slippage or destAmount': ValidationFailedError,
    'Source Amount Mismatch': ValidationFailedError,
    'Destination Amount Mismatch': ValidationFailedError,
    'Source Token Mismatch': ValidationFailedError,
    'Destination Token Mismatch': ValidationFailedError,
    'Error Parsing params': ValidationFailedError,
    'priceRoute must be unmodified as sent by the price endpoint': ValidationFailedError,
    'Unable to process the transaction': EstimationError,
    'ERROR_BUILDING_TRANSACTION': EstimationError,
}


class ParaSwapProviderV5(BaseProvider):
    """
    Trading Provider for Paraswap v5 dex aggregator
    Docs: https://developers.paraswap.network/api/master
    """

    MAIN_API_URL: yarl.URL = yarl.URL('https://api.paraswap.io/')
    VERSION = 6.2
    with open(Path(__file__).parent / 'config.json') as f:
        PROVIDER_NAME = ujson.load(f)['name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.get_swap_price = cached(
            ttl=30, **get_cache_config(self.config), noself=True
        )(self.get_swap_price)

    async def request(self, method: str, path: str, *args, **kwargs):
        request_function = getattr(self.aiohttp_session, method.lower())
        url = self.MAIN_API_URL / path
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
        **kwargs,
    ):
        path = 'prices'
        params = {
            'srcToken': sell_token,
            'destToken': buy_token,
            'amount': sell_amount,
            'side': 'SELL',
            'network': chain_id,
            'otherExchangePrices': 'false',
            'partner': self.config.PARTNER,
            'srcDecimals': kwargs.get('src_decimals'),
            'destDecimals': kwargs.get('dest_decimals'),
            'version': self.VERSION,
        }

        try:
            quotes = await self.request(method='get', path=path, params=params)
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
        response = self._convert_response_from_swap_price(quotes)
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
        **kwargs,
    ) -> Optional[ProviderQuoteResponse]:
        params = {
            'srcToken': sell_token,
            'destToken': buy_token,
            'amount': sell_amount,
            'side': 'SELL',
            'network': chain_id,
            'otherExchangePrices': 'false',
            'partner': self.config.PARTNER,
            'version': self.VERSION,
            'srcDecimals': kwargs.get('src_decimals'),
            'destDecimals': kwargs.get('dest_decimals'),
        }
        if taker_address:
            params['userAddress'] = taker_address
        try:
            response = await self.request(method='get', path='prices', params=params)
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ServerDisconnectedError,
        ) as e:
            e = self.handle_exception(
                e, method='get_swap_quote', params=params, chain_id=chain_id
            )
            raise e

        price_route = response['priceRoute']
        ignore_checks = str(ignore_checks).lower()
        params = {'network': price_route['network'], 'ignoreChecks': ignore_checks}
        if gas_price is not None:
            params['gasPrice'] = gas_price
        data = {
            'srcToken': sell_token,
            'destToken': buy_token,
            'srcAmount': str(sell_amount),
            'priceRoute': price_route,
            'userAddress': taker_address,
            'partner': self.config.PARTNER,
            'srcDecimals': price_route['srcDecimals'],
            'destDecimals': price_route['destDecimals'],
        }

        if buy_token_percentage_fee:
            data['partnerFeeBps'] = int(
                buy_token_percentage_fee * 10000
            )  # 100% -> 10000
        if slippage_percentage:
            data['slippage'] = int(slippage_percentage * 10000)  # 100% -> 10000
        else:
            data['destAmount'] = (str(price_route['destAmount']),)

        if fee_recipient:
            data['partnerAddress'] = fee_recipient

        try:
            response = await self.request(
                method='post',
                path=f'transactions/{price_route["network"]}',
                params=params,
                json=data,
            )
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ServerDisconnectedError,
        ) as e:
            e = self.handle_exception(
                e, response=response, data=data, params=params, chain_id=chain_id
            )
            raise e
        return self._convert_response_from_swap_quote(response, price_route)

    def _convert_response_from_swap_quote(
        self,
        quote_response: dict,
        price_response: dict,
        **kwargs,
    ) -> Optional[ProviderQuoteResponse]:
        price = Decimal(price_response['destAmount']) / Decimal(
            price_response['srcAmount']
        )
        sources = self.convert_sources_for_meta_aggregation(price_response['bestRoute'])
        try:
            prepared_response = ProviderQuoteResponse(
                sources=sources,
                buy_amount=str(price_response['destAmount']),
                gas=quote_response.get('gas', '0'),
                sell_amount=price_response['srcAmount'],
                to=quote_response['to'],
                data=quote_response['data'],
                gas_price=quote_response['gasPrice'],
                value=quote_response['value'],
                price=str(price),
            )
        except (KeyError, ValidationError) as e:
            e = self.handle_exception(
                e,
                response=quote_response,
                method='_convert_response_from_swap_quote',
                price_response=price,
                **kwargs,
            )
            raise e
        return prepared_response

    def _convert_response_from_swap_price(
        self, price_response: dict
    ) -> Optional[ProviderPriceResponse]:
        price_response = price_response['priceRoute']
        dst_amount = (
            Decimal(price_response['destAmount']) / 10 ** price_response['destDecimals']
        )
        src_amount = (
            Decimal(price_response['srcAmount']) / 10 ** price_response['srcDecimals']
        )
        price = dst_amount / src_amount
        sources = self.convert_sources_for_meta_aggregation(price_response['bestRoute'])
        try:
            prepared_response = ProviderPriceResponse(
                provider=self.PROVIDER_NAME,
                sources=sources,
                buy_amount=str(price_response['destAmount']),
                gas=price_response['gasCost'],
                sell_amount=price_response['srcAmount'],
                gas_price='0',
                value='0',
                price=str(price),
                allowance_target=price_response['tokenTransferProxy'],
            )
        except (KeyError, ValidationError) as e:
            e = self.handle_exception(
                e, response=price_response, method='_convert_response_from_swap_price'
            )
            raise e
        else:
            return prepared_response

    @staticmethod
    def convert_sources_for_meta_aggregation(
        sources: Optional[Union[dict, list[dict]]],
    ) -> Optional[list[SwapSources]]:
        if not sources:
            return
        swaps = list(chain.from_iterable([i['swaps'] for i in sources]))
        swap_exchanges = [i['swapExchanges'] for i in swaps]
        sources_list = list(chain.from_iterable(i for i in swap_exchanges))
        converted_sources = []
        for source in sources_list:
            converted_sources.append(
                SwapSources(name=source['exchange'], proportion=source['percent'])
            )
        return converted_sources

    def handle_exception(
        self, exception: Union[ClientResponseError, KeyError, ValidationError], **kwargs
    ) -> BaseAggregationProviderError:
        """
        exception.message: '{'error': 'Not enough liquidity for this trade'}'
        """
        exc = super().handle_exception(exception, **kwargs)
        if exc:
            logger.error(*exc.to_log_args(), extra=exc.to_dict())
            return exc
        msg = ujson.loads(exception.message).get('error', 'Unknown error')
        for error, error_class in PARASWAP_ERRORS.items():
            if re.search(error.lower(), msg.lower()):
                break
        else:
            error_class = AggregationProviderError
        exc = error_class(
            self.PROVIDER_NAME,
            msg,
            url=str(exception.request_info.url),
            **kwargs,
        )
        if isinstance(exc, EstimationError):
            logger.warning(
                f'potentially blacklist. %({LogArgs.token_idx})',
                {
                    LogArgs.token_idx: f"{kwargs.get('token_address')}"
                    f"-{kwargs.get('chain_id')}"
                },
                extra={
                    'token_address': kwargs.get('token_address'),
                    'chain_id': kwargs.get('chain_id'),
                },
            )
        logger.warning(*exc.to_log_args(), extra=exc.to_dict())
        return exc
