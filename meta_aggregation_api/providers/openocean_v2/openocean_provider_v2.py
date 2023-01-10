import asyncio
import ssl
from _decimal import Decimal
from pathlib import Path
from typing import Optional

import ujson
from aiohttp import ClientResponse, ClientResponseError, ServerDisconnectedError
from pydantic import ValidationError

from meta_aggregation_api.config import config
from meta_aggregation_api.models.meta_agg_models import (ProviderQuoteResponse,
                                                         ProviderPriceResponse)
from meta_aggregation_api.models.provider_response_models import SwapSources
from meta_aggregation_api.providers.base_provider import BaseProvider
from meta_aggregation_api.utils.errors import BaseAggregationProviderError
from meta_aggregation_api.utils.logger import get_logger

logger = get_logger(__name__)


class OpenOceanProviderV2(BaseProvider):
    """https://docs.openocean.finance/dev/openocean-api-3.0/api-reference"""
    TRADING_API = 'https://ethapi.openocean.finance/v2'

    with open(Path(__file__).parent / 'config.json') as f:
        PROVIDER_NAME = ujson.load(f)['name']

    async def _get_response(self, url: str, params: Optional[dict] = None) -> dict:
        async with self.aiohttp_session.get(
            url, params=params, timeout=self.REQUEST_TIMEOUT, ssl=ssl.SSLContext()
        ) as response:
            response: ClientResponse
            logger.debug(f'Request GET {response.url}')
            data = await response.json()
            try:
                response.raise_for_status()
            except ClientResponseError as e:
                # Fix bug with HTTP status code 0.
                status = 500 if e.status not in range(100, 600) else e.status
                data['source'] = 'proxied OpenOcean API'
                raise ClientResponseError(
                    request_info=e.request_info,
                    history=e.history,
                    status=status,
                    # Hack for error init method: expected str, but list and dict also works.
                    message=[data],
                    headers=e.headers
                )
        return data

    async def get_swap_price(
        self,
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        chain_id: int,
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = 1,
        taker_address: Optional[str] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None,
    ):
        url = '%s/%s/quote' % (self.TRADING_API, chain_id)
        params = {
            'inTokenAddress': sell_token,
            'outTokenAddress': buy_token,
            'amount': sell_amount,
        }
        if gas_price:
            params['gasPrice'] = gas_price
        if taker_address:
            params['account'] = taker_address
        if fee_recipient:
            params['referrer'] = fee_recipient
        if buy_token_percentage_fee:
            params['referrerFee'] = buy_token_percentage_fee * 100
        try:
            response = await self._get_response(url, params)
        except (
            ClientResponseError, asyncio.TimeoutError, ServerDisconnectedError) as e:
            exc = self.handle_exception(e, params=params, token_address=sell_token,
                                        chain_id=chain_id)
            raise exc
        return self._convert_response_from_swap_price(response, gas_price, url=url)

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
    ) -> ProviderQuoteResponse:
        url = '%s/%s/swap' % (self.TRADING_API, chain_id)
        params = {
            'inTokenAddress': sell_token,
            'outTokenAddress': buy_token,
            'amount': sell_amount,
            'account': taker_address,
        }
        if gas_price:
            params['gasPrice'] = gas_price
        if fee_recipient:
            params['referrer'] = fee_recipient
        if buy_token_percentage_fee:
            params['referrerFee'] = buy_token_percentage_fee * 100
        try:
            response = await self._get_response(url, params)
        except (
            ClientResponseError, asyncio.TimeoutError, ServerDisconnectedError) as e:
            exc = self.handle_exception(e, params=params, token_address=sell_token,
                                        chain_id=chain_id)
            raise exc
        return self._convert_response_from_swap_quote(response)

    def _convert_response_from_swap_price(
        self,
        response: dict,
        gas_price: int,
        **kwargs,
    ) -> ProviderPriceResponse:
        sources = self.convert_sources_for_meta_aggregation(response['path']['routes'])
        value = '0'
        sell_amount = Decimal(response['inAmount']) / 10 ** Decimal(response['inToken']['decimals'])
        buy_amount = Decimal(response['outAmount']) / 10 ** Decimal(response['outToken']['decimals'])
        price = buy_amount / sell_amount
        if response['inToken']['address'] == config.NATIVE_TOKEN_ADDRESS:
            value = response['inAmount']
        try:
            return ProviderPriceResponse(
                provider=self.PROVIDER_NAME,
                sources=sources,
                buy_amount=response['outAmount'],
                sell_amount=response['inAmount'],
                gas=response['estimatedGas'],
                gas_price=str(gas_price),
                value=value,
                price=str(price),
            )
        except (KeyError, ValidationError) as e:
            e = self.handle_exception(e, response=response,
                                      method='_convert_response_from_swap_quote',
                                      price=price, **kwargs)
            raise e

    def _convert_response_from_swap_quote(self, response: dict) -> ProviderQuoteResponse:
        sell_amount = Decimal(response['inAmount']) / 10 ** Decimal(response['inToken']['decimals'])
        buy_amount = Decimal(response['outAmount']) / 10 ** Decimal(response['outToken']['decimals'])
        price = buy_amount / sell_amount
        try:
            return ProviderQuoteResponse(
                sources=[],
                buy_amount=response['outAmount'],
                sell_amount=response['inAmount'],
                gas=response['estimatedGas'],
                gas_price=response['gasPrice'],
                value=response['value'],
                price=str(price),
                data=response['data'],
                to=response['to'],
            )
        except (KeyError, ValidationError) as e:
            e = self.handle_exception(e, response=response,
                                      method='_convert_response_from_swap_quote')
            raise e

    @staticmethod
    def convert_sources_for_meta_aggregation(sources: list) -> list:
        converted_sources = []
        for source in sources:
            for route in source.get('subRoutes', []):
                for dex in route.get('dexes', []):
                    converted_sources.append(SwapSources(
                        name=dex['dex'],
                        proportion=dex['percentage'],
                    ))
        return converted_sources

    def handle_exception(self, e, **kwargs) -> BaseAggregationProviderError:
        e = super().handle_exception(e, **kwargs)
        logger.error(e)
        return e
