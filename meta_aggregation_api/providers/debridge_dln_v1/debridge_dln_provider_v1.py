import asyncio
import json
import os
import ssl
from _decimal import Decimal
from pathlib import Path
from typing import Optional, Union, List, Dict

import ujson
from aiohttp import ClientResponse, ClientResponseError, ServerDisconnectedError
from pydantic import ValidationError

from meta_aggregation_api.models.meta_agg_models import (
    ProviderPriceResponse,
    ProviderQuoteResponse,
)
from meta_aggregation_api.models.provider_response_models import SwapSources
from meta_aggregation_api.providers.base_crosschain_provider import CrossChainProvider
from meta_aggregation_api.utils.errors import (
    AggregationProviderError,
    BaseAggregationProviderError,
)
from meta_aggregation_api.utils.logger import get_logger

logger = get_logger(__name__)


class DebridgeDlnProviderV1(CrossChainProvider):
    """https://docs.debridge.finance"""

    TRADING_API = os.environ.get('DEBRIDGE_TRADING_API', 'https://api.dln.trade/v1.0/dln/order')
    ORDER_API = os.environ.get('DEBRIDGE_ORDER_API', 'https://dln-api.debridge.finance/api')

    with open(Path(__file__).parent / 'config.json') as f:
        PROVIDER_NAME = ujson.load(f)['name']

    def is_require_gas_price(self) -> bool:
        return True

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
                data['source'] = 'proxied DEBRIDGE DLN API'
                raise ClientResponseError(
                    request_info=e.request_info,
                    history=e.history,
                    status=status,
                    # Hack for error init method: expected str, but list and dict also works.
                    message=[data],
                    headers=e.headers,
                )
        return data

    async def _post_response(self, url: str, params: Optional[dict] = None) -> dict:
        headers = {
            'Content-Type': 'application/json',
        }
        data = json.dumps(params)
        async with self.aiohttp_session.post(
            url, data=data, headers=headers, timeout=self.REQUEST_TIMEOUT, ssl=ssl.SSLContext()
        ) as response:
            response: ClientResponse
            logger.debug(f'Request POST {response.url}')
            data = await response.json()
            try:
                response.raise_for_status()
            except ClientResponseError as e:
                # Fix bug with HTTP status code 0.
                status = 500 if e.status not in range(100, 600) else e.status
                data['source'] = 'proxied Debridge API'
                raise ClientResponseError(
                    request_info=e.request_info,
                    history=e.history,
                    status=status,
                    # Hack for error init method: expected str, but list and dict also works.
                    message=[data],
                    headers=e.headers,
                )
        return data

    async def get_swap_price(
        self,
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        chain_id_from: int,
        chain_id_to: int,
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = 1,
        taker_address: Optional[str] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None,
    ):
        if buy_token.lower() == self.config.NATIVE_TOKEN_ADDRESS:
            buy_token = '0x0000000000000000000000000000000000000000'

        if sell_token.lower() == self.config.NATIVE_TOKEN_ADDRESS:
            sell_token = '0x0000000000000000000000000000000000000000'

        affiliate_fee_percent = 0
        if buy_token_percentage_fee is not None:
            affiliate_fee_percent = int(buy_token_percentage_fee * 100)

        url = '%s/quote' % (self.TRADING_API)
        params = {
            'srcChainId': chain_id_from,
            'srcChainTokenIn': sell_token,
            'srcChainTokenInAmount': sell_amount,
            'dstChainId': chain_id_to,
            'dstChainTokenOut': buy_token,
            'affiliateFeePercent': affiliate_fee_percent,
            'prependOperatingExpenses': 'true',
        }
        try:
            response = await self._get_response(url, params)
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ServerDisconnectedError,
        ) as e:
            exc = self.handle_exception(
                e, params=params, token_address=sell_token, give_chain_id=chain_id_from,
                take_chain_id=chain_id_to
            )
            raise exc
        return self._convert_response_from_swap_price(response)

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
        if buy_token.lower() == self.config.NATIVE_TOKEN_ADDRESS:
            buy_token = '0x0000000000000000000000000000000000000000'

        if sell_token.lower() == self.config.NATIVE_TOKEN_ADDRESS:
            sell_token = '0x0000000000000000000000000000000000000000'

        affiliate_fee_percent = 0
        if buy_token_percentage_fee is not None:
            affiliate_fee_percent = int(buy_token_percentage_fee * 100)

        url = '%s/create-tx' % (self.TRADING_API)
        params = {
            'srcChainId': chain_id_from,
            'srcChainTokenIn': sell_token,
            'srcChainTokenInAmount': sell_amount,
            'dstChainId': chain_id_to,
            'dstChainTokenOut': buy_token,
            'affiliateFeePercent': affiliate_fee_percent,
            "affiliateFeeRecipient": fee_recipient,
            'dstChainTokenOutAmount': 'auto',
            'srcChainOrderAuthorityAddress': taker_address,
            'dstChainTokenOutRecipient': taker_address,
            'dstChainOrderAuthorityAddress': taker_address,
        }

        try:
            response = await self._get_response(url, params)
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ServerDisconnectedError,
        ) as e:
            exc = self.handle_exception(
                e, params=params, token_address=sell_token, chain_id=chain_id_from
            )
            raise exc
        return self._convert_response_from_swap_quote(response)

    def _convert_response_from_swap_price(
        self, response: dict
    ) -> ProviderPriceResponse:
        estimation = response['estimation']
        sell_amount = Decimal(estimation['srcChainTokenIn']['amount']) / 10 ** Decimal(
            estimation['srcChainTokenIn']['decimals']
        )
        buy_amount = Decimal(estimation['dstChainTokenOut']['amount']) / 10 ** Decimal(
            estimation['dstChainTokenOut']['decimals']
        )
        price = buy_amount / sell_amount
        try:
            return ProviderPriceResponse(
                provider=self.PROVIDER_NAME,
                sources=[],
                buy_amount=estimation['dstChainTokenOut']['amount'],
                sell_amount=estimation['srcChainTokenIn']['amount'],
                gas='0',
                gas_price='0',
                value='0',
                price=str(price),
                allowance_target=response['tx']['allowanceTarget'],
            )
        except (KeyError, ValidationError) as e:
            e = self.handle_exception(
                e, response=response, method='_convert_response_from_swap_quote'
            )
            raise e

    def _convert_response_from_swap_quote(
        self, response: dict
    ) -> ProviderQuoteResponse:
        estimation = response['estimation']
        sell_amount = Decimal(estimation['srcChainTokenIn']['amount']) / 10 ** Decimal(
            estimation['srcChainTokenIn']['decimals']
        )
        buy_amount = Decimal(estimation['dstChainTokenOut']['amount']) / 10 ** Decimal(
            estimation['dstChainTokenOut']['decimals']
        )
        price = buy_amount / sell_amount
        tx = response['tx']
        try:
            return ProviderQuoteResponse(
                sources=[],
                buy_amount=estimation['dstChainTokenOut']['amount'],
                sell_amount=estimation['srcChainTokenIn']['amount'],
                gas_price=0,
                gas=0,
                value=tx['value'],
                price=str(price),
                data=tx['data'],
                to=tx['to'],
            )
        except (KeyError, ValidationError) as e:
            e = self.handle_exception(
                e, response=response, method='_convert_response_from_swap_quote'
            )
            raise e

    @staticmethod
    def convert_sources_for_meta_aggregation(sources: list) -> list:
        converted_sources = []
        for source in sources:
            for route in source.get('subRoutes', []):
                for dex in route.get('dexes', []):
                    converted_sources.append(
                        SwapSources(
                            name=dex['dex'],
                            proportion=dex['percentage'],
                        )
                    )
        return converted_sources

    async def get_orders_by_trader(
        self,
        *,
        chain_id: Optional[int],
        trader: str,
        maker_token: Optional[str] = None,
        taker_token: Optional[str] = None,
        statuses: Optional[List[str]] = None,
    ) -> List[Optional[Dict]]:
        url = '%s/Orders/filteredList' % (self.ORDER_API)
        params = {
            "giveChainIds": [chain_id],
            "orderStates": [],
            "creator": trader,
            "skip": 0,
            "take": 1000000,
        }

        try:
            response = await self._post_response(url, params)
            return response
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ServerDisconnectedError,
        ) as e:
            exc = self.handle_exception(
                e, params=params
            )
            raise exc

    async def get_order_by_hash(
        self,
        chain_id: Optional[int],
        order_hash: str,
    ) -> Optional[Dict[str, List[Dict]]]:
        url = '%s/%s' % (self.TRADING_API, order_hash)

        try:
            response = await self._get_response(url, {})
            return response
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ServerDisconnectedError,
        ) as e:
            exc = self.handle_exception(
                e, url=url
            )
            raise exc

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
        exc = AggregationProviderError(
            self.PROVIDER_NAME,
            msg,
            **kwargs,
        )
        return exc
