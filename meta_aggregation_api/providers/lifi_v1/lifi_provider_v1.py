import asyncio
import ssl
from _decimal import Decimal
from pathlib import Path
from typing import Optional, Union, List

import ujson
from aiocache import cached
from aiohttp import ClientResponse, ClientResponseError, ServerDisconnectedError
from pydantic import ValidationError

from meta_aggregation_api.config import config
from meta_aggregation_api.models.meta_agg_models import (ProviderPriceResponse,
                                                         ProviderQuoteResponse,
                                                         BridgePriceResponse)
from meta_aggregation_api.models.provider_response_models import SwapSources
from meta_aggregation_api.providers.base_provider import BaseProvider
from meta_aggregation_api.utils.cache import get_cache_config
from meta_aggregation_api.utils.errors import (BaseAggregationProviderError,
                                               AggregationProviderError)
from meta_aggregation_api.utils.logger import get_logger

logger = get_logger(__name__)


class LiFiProviderV1(BaseProvider):
    """https://apidocs.li.fi/reference/welcome-to-the-lifinance-api"""

    TRADING_API = 'https://li.quest'
    VERSION = '1'
    FEE = '0.0095'

    with open(Path(__file__).parent / 'config.json') as f:
        PROVIDER_NAME = ujson.load(f)['name']

    async def _get_response(self, url: str, params: Optional[dict] = None) -> dict:
        async with self.aiohttp_session.post(
            url, json=params, timeout=self.REQUEST_TIMEOUT, ssl=ssl.SSLContext(),
            headers={'Accept-Version': self.VERSION, 'accept': 'application/json',
                     'content-type': 'application/json'}
        ) as response:
            response: ClientResponse
            logger.debug(f'Request GET {response.url}')
            data = await response.json()
            try:
                response.raise_for_status()
            except ClientResponseError as e:
                # Fix bug with HTTP status code 0.
                status = 500 if e.status not in range(100, 600) else e.status
                data['source'] = 'proxied LiFi API'
                raise ClientResponseError(
                    request_info=e.request_info,
                    history=e.history,
                    status=status,
                    # Hack for error init method: expected str, but list and dict also works.
                    message=[data],
                    headers=e.headers
                )
        return data

    @cached(ttl=30, **get_cache_config())
    async def get_swap_price(
        self,
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        chain_id: int,
        to_chain_id: int = None,
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = None,
        taker_address: Optional[str] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None,
    ) -> ProviderPriceResponse:
        response = await self._make_request(

            buy_token=buy_token,
            sell_token=sell_token,
            sell_amount=sell_amount,
            chain_id=chain_id,
            to_chain_id=to_chain_id,
            taker_address=taker_address,
            gas_price=gas_price,
            slippage_percentage=slippage_percentage,
            fee_recipient=fee_recipient,
            buy_token_percentage_fee=buy_token_percentage_fee,
        )

        return self._convert_response_from_swap_price(
            response,
            sell_token_address=sell_token,
            buy_token_address=buy_token,
        )

    async def get_swap_quote(
        self,
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        taker_address: str,
        chain_id: int,
        to_chain_id: int = None,
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None
    ) -> ProviderQuoteResponse:
        if not taker_address:
            raise ValueError('Taker address is required')
        response = await self._make_request(
            buy_token=buy_token,
            sell_token=sell_token,
            sell_amount=sell_amount,
            chain_id=chain_id,
            to_chain_id=to_chain_id,
            taker_address=taker_address,
            gas_price=gas_price,
            slippage_percentage=slippage_percentage,
            fee_recipient=fee_recipient,
            buy_token_percentage_fee=buy_token_percentage_fee,
        )
        return self._convert_response_from_swap_quote(response, sell_token, buy_token)

    def _convert_response_from_swap_quote(
        self,
        response: dict,
        sell_token_address: str,
        buy_token_address: str,
    ) -> ProviderQuoteResponse:
        sources = []
        # sources = self._convert_sources_for_meta_aggregation(response['swaps'])
        for route in response['routes']:

            value = '0'
            if sell_token_address.lower() == config.NATIVE_TOKEN_ADDRESS:
                value = response['fromToken']
            sell_token_decimals = route['fromToken']['decimals']
            buy_token_decimals = route['toToken']['decimals']
            sell_amount = Decimal(route['fromAmount']) / 10 ** sell_token_decimals
            buy_amount = Decimal(route['toAmount']) / 10 ** buy_token_decimals
            price = buy_amount / sell_amount



            try:
                return ProviderQuoteResponse(
                    sources=route['steps'],
                    buy_amount=buy_amount,
                    gas=0,
                    sell_amount=sell_amount,
                    gas_price=0,
                    value=value,
                    price=price,
                    to=response['routerAddress'],
                    data=response['encodedSwapData'],
                )
            except (KeyError, ValidationError) as e:
                e = self.handle_exception(e)
                raise e

    async def _make_request(
        self,
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        chain_id: int,
        to_chain_id: int,
        taker_address: str,
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None
    ):
        url = f'{self.TRADING_API}/v{self.VERSION}/advanced/routes/'
        params = {
            'fromChainId': chain_id,
            'fromTokenAddress': sell_token,
            'toChainId': to_chain_id,
            'toTokenAddress': buy_token,
            'fromAmount': str(sell_amount),
            'fromAddress': taker_address,
            'toAddress': taker_address,
            'saveGas': 0,
            'gasInclude': 0,
        }
        # TODO: Delete after integration
        config.PARTNER = None
        if config.PARTNER:
            params['options'] = {'integrator': config.PARTNER, 'fee': self.FEE,
                                 'referrer': fee_recipient}

        try:
            response = await self._get_response(url, params)
        except (
                ClientResponseError, asyncio.TimeoutError, ServerDisconnectedError
        ) as e:
            exc = self.handle_exception(e, params=params, token_address=sell_token,
                                        chain_id=chain_id)
            raise exc
        return response

    def _convert_response_from_swap_price(
        self,
        response: dict,
        sell_token_address: str,
        buy_token_address: str,
    ) -> List[BridgePriceResponse]:
        providers = []
        for route in response['routes']:
            value = '0'
            if sell_token_address.lower() == config.NATIVE_TOKEN_ADDRESS:
                value = route['fromAmount']
            sell_token_decimals = route['fromToken']['decimals']
            buy_token_decimals = route['toToken']['decimals']
            sell_amount = Decimal(route['fromAmount']) / 10 ** sell_token_decimals
            buy_amount = Decimal(route['toAmount']) / 10 ** buy_token_decimals
            price = buy_amount / sell_amount
            try:
                providers.append(BridgePriceResponse(
                        provider=self.PROVIDER_NAME,
                        route=route['id'],
                        sources=route['steps'],
                        buy_amount=route['toAmount'],
                        sell_amount=route['fromAmount'],
                        value=value,
                        price=price,
                        is_best=True if 'RECOMMENDED' in route['tags'] else False
                    ))
            except (KeyError, ValidationError) as e:
                e = self.handle_exception(e)
                raise e
        return providers

    def _convert_sources_for_meta_aggregation(self, sources: list) -> list[SwapSources]:
        converted_sources = []
        for source in sources:
            for sub_source in source:
                try:
                    converted_sources.append(
                        SwapSources(
                            name=sub_source['exchange'],
                            proportion=0.0,
                        )
                    )
                except (KeyError, ValidationError) as e:
                    e = self.handle_exception(e)
                    raise e
        return converted_sources

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
