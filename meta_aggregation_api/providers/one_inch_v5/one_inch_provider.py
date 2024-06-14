import asyncio
import re
import ssl
from itertools import chain
from pathlib import Path
from typing import Dict, List, Optional, Union

import aiohttp
import ujson
from aiocache import cached
from aiohttp import ClientResponse, ClientResponseError, ServerDisconnectedError
from pydantic import ValidationError
from yarl import URL

from meta_aggregation_api.clients.apm_client import ApmClient
from meta_aggregation_api.config import Config
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
    InsufficientLiquidityError,
    TokensError,
    UserBalanceError,
)
from meta_aggregation_api.utils.logger import LogArgs, get_logger

LIMIT_ORDER_VERSION = 3.0
DEFAULT_SLIPPAGE_PERCENTAGE = 0.5

ONE_INCH_ERRORS = {
    'insufficient liquidity': InsufficientLiquidityError,
    'cannot estimate': EstimationError,
    'fromtokenaddress cannot be equals to totokenaddress': TokensError,
    'not enough \w+ balance': UserBalanceError,
    'not enough allowance': AllowanceError,
    'cannot sync \w+': TokensError,
}

MAX_RESULT_PRESET = {
    'complexityLevel': 2,
    'mainRouteParts': 10,
    'parts': 50,
    'virtualParts': 50,
}

LOWEST_GAS_PRESET = {
    'complexityLevel': 1,
    'mainRouteParts': 1,
    'parts': 1,
    'virtualParts': 1,
}

AMM_MAPPING = {
    'SUSHI': 'SushiSwap',
}

logger = get_logger(__name__)


class OneInchProviderV5(BaseProvider):
    """
    Trading and limit orders Provider for 1Inch. Docs: https://docs.1inch.io/docs/1inch-network-overview

    URL structures:
        Trading:      https://{trading_api_domain}/v{version}/{chain_id}/{operation}?queryParams
        Limit orders: https://{limit_orders_domain}/v{version}/{chain_id}/limit_order/{operation}?queryParams
    """

    LIMIT_ORDERS_DOMAIN = 'api.1inch.dev/orderbook'
    TRADING_API_DOMAIN = 'api.1inch.dev/swap'
    TRADING_API_VERSION = 5.0
    with open(Path(__file__).parent / 'config.json') as f:
        PROVIDER_NAME = ujson.load(f)['name']

    def __init__(
        self,
        *,
        config: Config,
        session: aiohttp.ClientSession,
        apm_client: ApmClient,
        **_,
    ) -> None:
        super().__init__(config=config, session=session, apm_client=apm_client)
        self.api_key = self.config.ONE_INCH_API_KEY
        self.get_swap_price = cached(
            ttl=30, **get_cache_config(self.config), noself=True
        )(self.get_swap_price)

    @classmethod
    def _limit_order_path_builder(
        cls,
        version: Union[int, float],
        path: str,
        endpoint: str,
        chain_id: int,
    ) -> URL:
        url = (
            URL(f'https://{cls.LIMIT_ORDERS_DOMAIN}')
            / f'v{version}'
            / str(chain_id)
            / path
            / endpoint
        )
        return url

    @classmethod
    def _trading_api_path_builder(
        cls,
        path: str,
        chain_id: int,
    ) -> URL:
        url = (
            URL(f'https://{cls.TRADING_API_DOMAIN}')
            / f'v{cls.TRADING_API_VERSION}'
            / str(chain_id)
            / path
        )
        return url

    async def get_response(
        self,
        url: URL,
        params: Optional[Dict],
        method: str = 'GET',
        body: Optional[Dict] = None,
    ) -> Union[List, Dict]:
        request_function = getattr(self.aiohttp_session, method.lower())
        async with request_function(
            str(url),
            params=params,
            timeout=self.REQUEST_TIMEOUT,
            ssl=ssl.SSLContext(),
            json=body,
            headers={'Authorization': 'Bearer ' + self.api_key},
        ) as response:
            response: ClientResponse
            logger.debug(f'Request GET {response.url}')
            data = await response.read()
            if not data:
                return {}
            data = ujson.loads(data)
            try:
                response.raise_for_status()
            except ClientResponseError as e:
                # Fix bug with HTTP status code 0.
                status = 500 if e.status not in range(100, 600) else e.status
                data['source'] = 'proxied 1inch API'
                raise ClientResponseError(
                    request_info=e.request_info,
                    history=e.history,
                    status=status,
                    # Hack for error init method: expected str, but list and dict also works.
                    message=[data],
                    headers=e.headers,
                )

        return data

    async def get_orders_by_trader(
        self,
        *,
        chain_id: Optional[int],
        trader: str,
        maker_token: Optional[str] = None,
        taker_token: Optional[str] = None,
        statuses: Optional[List[str]] = None,
    ) -> List[Optional[Dict]]:
        """
        Docs: https://limit-orders.1inch.exchange/swagger/ethereum/#/default/ModuleController_getLimitOrder
        """
        path = 'address'
        endpoint = trader
        url = self._limit_order_path_builder(
            version=LIMIT_ORDER_VERSION,
            endpoint=endpoint,
            path=path,
            chain_id=chain_id,
        )
        query = {
            'limit': 100,
            'page': 1,
            'sortBy': 'createDateTime',
        }
        if maker_token:
            query['makerAsset'] = maker_token
        if taker_token:
            query['takerAsset'] = taker_token
        if statuses:
            query['statuses'] = statuses
        try:
            response = await self.get_response(url, query)
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ServerDisconnectedError,
        ) as e:
            e = self.handle_exception(e, params=query, wallet=trader)
            raise e
        return response

    async def get_order_by_hash(
        self,
        chain_id: Optional[int],
        order_hash: str,
    ) -> Optional[Dict[str, List[Dict]]]:
        path = 'events'
        endpoint = order_hash
        url = self._limit_order_path_builder(
            version=LIMIT_ORDER_VERSION,
            endpoint=endpoint,
            path=path,
            chain_id=chain_id,
        )
        try:
            response = await self.get_response(url, None)
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ServerDisconnectedError,
        ) as e:
            e = self.handle_exception(e)
            raise e
        return response

    async def post_limit_order(
        self,
        chain_id: Optional[int],
        order_hash: str,
        signature: str,
        data: Dict,
    ):
        method = 'POST'
        path = ''
        endpoint = ''
        url = self._limit_order_path_builder(
            version=LIMIT_ORDER_VERSION,
            endpoint=endpoint,
            path=path,
            chain_id=chain_id,
        )
        body = {
            'orderHash': order_hash,
            'signature': signature,
            'data': data,
        }
        try:
            response = await self.get_response(url, None, method, body)
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ServerDisconnectedError,
        ) as e:
            e = self.handle_exception(e)
            raise e
        return response

    async def get_swap_price(
        self,
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        chain_id: Optional[int] = None,
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = 1,
        taker_address: Optional[str] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None,
        **_,
    ):
        path = 'quote'
        url = self._trading_api_path_builder(
            path=path,
            chain_id=chain_id,
        )
        query = {
            'toTokenAddress': buy_token,
            'fromTokenAddress': sell_token,
            'amount': sell_amount,
        }
        if gas_price:
            query['gasPrice'] = str(gas_price)

        if buy_token_percentage_fee:
            query['fee'] = buy_token_percentage_fee
        query.update(MAX_RESULT_PRESET)
        try:
            response = await self.get_response(url, query)
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ServerDisconnectedError,
        ) as e:
            e = self.handle_exception(
                e, params=query, token_address=sell_token, chain_id=chain_id
            )
            raise e
        sell_amount = int(sell_amount) / 10 ** response['fromToken']['decimals']
        buy_amount = (
            int(response['toTokenAmount']) / 10 ** response['toToken']['decimals']
        )
        price = buy_amount / sell_amount
        value = '0'
        if sell_token.lower() == self.config.NATIVE_TOKEN_ADDRESS:
            value = str(sell_amount)
        try:
            sources = self.convert_sources_for_meta_aggregation(response['protocols'])
            res = ProviderPriceResponse(
                provider=self.PROVIDER_NAME,
                sources=sources,
                buy_amount=response['toTokenAmount'],
                gas=response['estimatedGas'],
                sell_amount=response['fromTokenAmount'],
                gas_price=gas_price if gas_price else '0',
                value=value,
                price=price,
            )
        except (KeyError, ValidationError) as e:
            e = self.handle_exception(
                e,
                response=response,
                method='_convert_response_from_swap_quote',
                price=price,
                url=url,
                params=query,
                chain_id=chain_id,
            )
            raise e
        return res

    async def get_swap_quote(
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
        ignore_checks: bool = False,
    ) -> Optional[ProviderQuoteResponse]:
        """https://docs.1inch.io/docs/aggregation-protocol/api/swap-params"""
        if not chain_id:
            raise ValueError('chain_id is required')

        if not slippage_percentage:
            slippage_percentage = DEFAULT_SLIPPAGE_PERCENTAGE
        else:
            slippage_percentage = (
                slippage_percentage * 100
            )  # 1inch awaits slippage in percents
        if not taker_address:
            raise ValueError('Taker address is required')

        path = 'swap'
        url = self._trading_api_path_builder(
            path=path,
            chain_id=chain_id,
        )
        ignore_checks = str(ignore_checks).lower()
        query = {
            'fromTokenAddress': sell_token,
            'toTokenAddress': buy_token,
            'amount': sell_amount,
            'fromAddress': taker_address,
            'slippage': slippage_percentage,
            'disableEstimate': ignore_checks,
        }
        if gas_price:
            query['gasPrice'] = gas_price

        if fee_recipient:
            query['referrerAddress'] = fee_recipient

        if buy_token_percentage_fee:
            query['fee'] = buy_token_percentage_fee
        query.update(MAX_RESULT_PRESET)
        try:
            response = await self.get_response(url, query)
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ServerDisconnectedError,
        ) as e:
            exc = self.handle_exception(
                e, params=query, token_address=sell_token, chain_id=chain_id
            )
            raise exc
        sell_amount = int(sell_amount) / 10 ** response['fromToken']['decimals']
        buy_amount = (
            int(response['toTokenAmount']) / 10 ** response['toToken']['decimals']
        )
        price = buy_amount / sell_amount
        return self._convert_response_from_swap_quote(
            response, price, url=url, query=query
        )

    def _convert_response_from_swap_quote(
        self,
        response: dict,
        price: float,
        **kwargs,
    ) -> Optional[ProviderQuoteResponse]:
        sources = self.convert_sources_for_meta_aggregation(response['protocols'])
        try:
            prepared_response = ProviderQuoteResponse(
                sources=sources,
                buy_amount=response['toTokenAmount'],
                gas=response['tx']['gas'],
                sell_amount=response['fromTokenAmount'],
                to=response['tx']['to'],
                data=response['tx']['data'],
                gas_price=response['tx']['gasPrice'],
                value=response['tx']['value'],
                price=str(price),
            )
        except (KeyError, ValidationError) as e:
            e = self.handle_exception(
                e,
                response=response,
                method='_convert_response_from_swap_quote',
                price=price,
                **kwargs,
            )
            raise e
        else:
            return prepared_response

    @staticmethod
    def convert_sources_for_meta_aggregation(
        sources: Optional[dict | list[dict]],
    ) -> list[SwapSources]:
        if not sources:
            return []
        sources_list = list(chain.from_iterable(chain.from_iterable(sources)))
        converted_sources = []
        for source in sources_list:
            source['name'] = AMM_MAPPING.get(source['name'], source['name'])
            converted_sources.append(
                SwapSources(name=source['name'], proportion=source['part'])
            )
        return converted_sources

    def handle_exception(
        self,
        exception: Union[ClientResponseError, KeyError, ValidationError],
        **kwargs,
    ) -> BaseAggregationProviderError:
        """
        exception.message: [
            {"code": 400, "description": "cannot estimate"}
        ]
        """
        exc = super().handle_exception(exception, **kwargs)
        if exc:
            logger.error(*exc.to_log_args(), extra=exc.to_dict())
            return exc
        msg = exception.message
        if isinstance(exception.message, list) and isinstance(
            exception.message[0], dict
        ):
            msg = exception.message[0].get(
                'description',
                exception.message[0].get(
                    'message', exception.message[0].get('error', '')
                ),
            )
        for error, error_class in ONE_INCH_ERRORS.items():
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
                f'potentially blacklist. %({LogArgs.token_idx})s',
                {
                    LogArgs.token_idx: f'{kwargs.get("token_address")}-{kwargs.get("chain_id")}'
                },
                extra={
                    'token_address': kwargs.get('token_address'),
                    'chain_id': kwargs.get('chain_id'),
                },
            )
        logger.warning(*exc.to_log_args(), extra=exc.to_dict())
        return exc
