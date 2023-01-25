import asyncio
import ssl
from pathlib import Path
from typing import Optional, Union

import ujson
from _decimal import Decimal
from aiocache import cached
from aiohttp import ClientResponse, ClientResponseError, ServerDisconnectedError
from pydantic import ValidationError

from meta_aggregation_api.config import config
from meta_aggregation_api.models.meta_agg_models import (
    ProviderPriceResponse,
    ProviderQuoteResponse,
)
from meta_aggregation_api.models.provider_response_models import SwapSources
from meta_aggregation_api.providers.base_provider import BaseProvider
from meta_aggregation_api.services.chains import chains
from meta_aggregation_api.utils.cache import get_cache_config
from meta_aggregation_api.utils.errors import (
    AggregationProviderError,
    BaseAggregationProviderError,
)
from meta_aggregation_api.utils.logger import get_logger

logger = get_logger(__name__)

CHAIN_ID_TO_NETWORK = {
    1: 'ethereum',
    56: 'bsc',
    137: 'polygon',
    10: 'optimism',
    42161: 'arbitrum',
    43114: 'avalanche',
    250: 'fantom',
}


class KyberSwapProviderV1(BaseProvider):
    """https://docs.kyberswap.com/Aggregator/aggregator-api"""

    TRADING_API = 'https://aggregator-api.kyberswap.com'
    VERSION = '1'

    with open(Path(__file__).parent / 'config.json') as f:
        PROVIDER_NAME = ujson.load(f)['name']

    async def _get_response(self, url: str, params: Optional[dict] = None) -> dict:
        async with self.aiohttp_session.get(
            url,
            params=params,
            timeout=self.REQUEST_TIMEOUT,
            ssl=ssl.SSLContext(),
            headers={'Accept-Version': self.VERSION},
        ) as response:
            response: ClientResponse
            logger.debug(f'Request GET {response.url}')
            data = await response.json()
            try:
                response.raise_for_status()
            except ClientResponseError as e:
                # Fix bug with HTTP status code 0.
                status = 500 if e.status not in range(100, 600) else e.status
                data['source'] = 'proxied KyberSwap API'
                raise ClientResponseError(
                    request_info=e.request_info,
                    history=e.history,
                    status=status,
                    # Hack for error init method: expected str, but list and dict also works.
                    message=[data],
                    headers=e.headers,
                )
        return data

    @cached(ttl=30, **get_cache_config())
    async def get_swap_price(
        self,
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        chain_id: int,
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
            chain_id=chain_id,
        )

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
        buy_token_percentage_fee: Optional[float] = None,
    ) -> ProviderQuoteResponse:
        if not taker_address:
            raise ValueError('Taker address is required')
        response = await self._make_request(
            buy_token=buy_token,
            sell_token=sell_token,
            sell_amount=sell_amount,
            chain_id=chain_id,
            taker_address=taker_address,
            gas_price=gas_price,
            slippage_percentage=slippage_percentage,
            fee_recipient=fee_recipient,
            buy_token_percentage_fee=buy_token_percentage_fee,
        )
        return self._convert_response_from_swap_quote(
            response, sell_token, buy_token, chain_id
        )

    def _convert_response_from_swap_quote(
        self,
        response: dict,
        sell_token_address: str,
        buy_token_address: str,
        chain_id: int,
    ) -> ProviderQuoteResponse:
        sources = self._convert_sources_for_meta_aggregation(response['swaps'])
        value = '0'
        if sell_token_address.lower() == config.NATIVE_TOKEN_ADDRESS:
            value = response['inputAmount']
            sell_token_decimals = chains.get_chain_by_id(chain_id).native_token.decimals
        else:
            sell_token_decimals = response['tokens'][sell_token_address.lower()][
                'decimals'
            ]
        if buy_token_address.lower() == config.NATIVE_TOKEN_ADDRESS:
            buy_token_decimals = chains.get_chain_by_id(chain_id).native_token.decimals
        else:
            buy_token_decimals = response['tokens'][buy_token_address.lower()][
                'decimals'
            ]
        sell_amount = Decimal(response['inputAmount']) / 10**sell_token_decimals
        buy_amount = Decimal(response['outputAmount']) / 10**buy_token_decimals
        price = buy_amount / sell_amount
        try:
            return ProviderQuoteResponse(
                sources=sources,
                buy_amount=response['outputAmount'],
                gas=response['totalGas'],
                sell_amount=response['inputAmount'],
                gas_price=str(int(Decimal(response['gasPriceGwei']) * 10**9)),
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
        taker_address: str,
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None,
    ):
        url = f'{self.TRADING_API}/{CHAIN_ID_TO_NETWORK[chain_id]}/route/encode'
        params = {
            'tokenIn': sell_token,
            'tokenOut': buy_token,
            'amountIn': str(sell_amount),
            'clientData': "{'source': '%s'}" % config.PARTNER,
        }
        if taker_address:
            params['to'] = taker_address
        else:
            # KyberSwap has only one endpoint that require taker address
            params['to'] = '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE'
        if slippage_percentage:
            params['slippageTolerance'] = str(
                int(slippage_percentage * 10000)
            )  # 0.1% == 10
        if buy_token_percentage_fee and fee_recipient:
            params['chargeFeeBy'] = 'currency_out'
            params['feeReceiver'] = fee_recipient
            params['isInBps'] = 1
            params['feeAmount'] = str(
                int(buy_token_percentage_fee * 10000)
            )  # 0.1% == 10

        try:
            response = await self._get_response(url, params)
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ServerDisconnectedError,
        ) as e:
            exc = self.handle_exception(
                e, params=params, token_address=sell_token, chain_id=chain_id
            )
            raise exc
        return response

    def _convert_response_from_swap_price(
        self,
        response: dict,
        sell_token_address: str,
        buy_token_address: str,
        chain_id: int,
    ) -> ProviderPriceResponse:
        sources = self._convert_sources_for_meta_aggregation(response['swaps'])
        value = '0'
        if sell_token_address.lower() == config.NATIVE_TOKEN_ADDRESS:
            value = response['inputAmount']
            sell_token_decimals = chains.get_chain_by_id(chain_id).native_token.decimals
        else:
            sell_token_decimals = response['tokens'][sell_token_address.lower()][
                'decimals'
            ]
        if buy_token_address.lower() == config.NATIVE_TOKEN_ADDRESS:
            buy_token_decimals = chains.get_chain_by_id(chain_id).native_token.decimals
        else:
            buy_token_decimals = response['tokens'][buy_token_address.lower()][
                'decimals'
            ]
        sell_amount = Decimal(response['inputAmount']) / 10**sell_token_decimals
        buy_amount = Decimal(response['outputAmount']) / 10**buy_token_decimals
        price = buy_amount / sell_amount
        try:
            return ProviderPriceResponse(
                provider=self.PROVIDER_NAME,
                sources=sources,
                buy_amount=response['outputAmount'],
                gas=response['totalGas'],
                sell_amount=response['inputAmount'],
                gas_price=str(int(Decimal(response['gasPriceGwei']) * 10**9)),
                value=value,
                price=price,
            )
        except (KeyError, ValidationError) as e:
            e = self.handle_exception(e)
            raise e

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
