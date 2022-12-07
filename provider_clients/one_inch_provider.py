import asyncio
import re
import ssl
from itertools import chain
from logging import DEBUG as LOG_DEBUG
from typing import Optional, Union, List, Dict

from aiohttp import ClientResponseError, ClientResponse, ServerDisconnectedError
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, before_log

from config import config
from models.meta_agg_models import SwapQuoteResponse, MetaSwapPriceResponse
from models.provider_response_models import SwapSources
from provider_clients.base_provider import BaseProvider
from utils.errors import EstimationError, AggregationProviderError, InsufficientLiquidityError, UserBalanceError, \
    AllowanceError, TokensError, BaseAggregationProviderError
from utils.logger import get_logger, LogArgs

LIMIT_ORDER_VERSION = 2.0
TRADING_API_VERSION = 5.0
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
    "complexityLevel": 2,
    "mainRouteParts": 10,
    "parts": 50,
    "virtualParts": 50,
}

LOWEST_GAS_PRESET = {
    "complexityLevel": 1,
    "mainRouteParts": 1,
    "parts": 1,
    "virtualParts": 1,
}

AMM_MAPPING = {
    'SUSHI': 'SushiSwap',
}

logger = get_logger(__name__)


# TODO: Add description, links to one inch docs

class OneInchProvider(BaseProvider):
    """
    Trading and limit orders proxy for 1Inch.
    URL structures:
        Trading:      https://{trading_api_domain}/v{version}/{chain_id}/{operation}?queryParams
        Limit orders: https://{limit_orders_domain}/v{version}/{chain_id}/limit_order/{operation}?queryParams
    """

    limit_orders_domain = 'limit-orders.1inch.io'
    trading_api_domain = 'api.1inch.io'
    limit_order = 'limit-order'
    _provider_name = 'one_inch'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @classmethod
    def _limit_order_path_builder(
            cls,
            version: Union[int, float],
            path: str,
            endpoint: str,
            chain_id: int,
    ) -> str:
        return f'https://{cls.limit_orders_domain}/v{version}/{chain_id}/{cls.limit_order}/{path}/{endpoint}'

    @classmethod
    def _trading_api_path_builder(
            cls,
            version: Union[int, float],
            path: str,
            chain_id: int,
    ) -> str:
        return f'https://{cls.trading_api_domain}/v{version}/{chain_id}/{path}'

    @retry(retry=(retry_if_exception_type(asyncio.TimeoutError) | retry_if_exception_type(ServerDisconnectedError)),
           stop=stop_after_attempt(3), reraise=True, before=before_log(logger, LOG_DEBUG))
    async def get_response(
            self,
            url: str,
            params: Optional[Dict],
    ) -> Union[List, Dict]:
        async with self.aiohttp_session.get(url, params=params, timeout=5, ssl=ssl.SSLContext()) as response:
            response: ClientResponse
            logger.debug(f'Request GET {response.url}')
            data = await response.json()
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
        except (ClientResponseError, asyncio.TimeoutError, ServerDisconnectedError) as e:
            e = self.handle_exception(e, url=url, params=query, wallet=trader)
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
        except (ClientResponseError, asyncio.TimeoutError, ServerDisconnectedError) as e:
            e = self.handle_exception(e, url=url)
            raise e
        return response

    async def get_swap_price(self, buy_token: str, sell_token: str, sell_amount: int,
                             chain_id: Optional[int] = None, affiliate_address: Optional[str] = None,
                             gas_price: Optional[int] = None, slippage_percentage: Optional[float] = 1,
                             taker_address: Optional[str] = None, fee_recipient: Optional[str] = None,
                             buy_token_percentage_fee: Optional[float] = None):
        path = 'quote'
        url = self._trading_api_path_builder(
            version=TRADING_API_VERSION,
            path=path,
            chain_id=chain_id,
        )
        query = {
            'toTokenAddress': buy_token,
            'fromTokenAddress': sell_token,
            'amount': sell_amount,
        }
        if gas_price:
            query['gasPrice'] = gas_price

        if buy_token_percentage_fee:
            query['fee'] = buy_token_percentage_fee
        query.update(MAX_RESULT_PRESET)
        try:
            response = await self.get_response(url, query)
        except (ClientResponseError, asyncio.TimeoutError, ServerDisconnectedError) as e:
            e = self.handle_exception(e, params=query, token_address=sell_token, chain_id=chain_id)
            raise e
        sell_amount = int(sell_amount) / 10 ** response['fromToken']['decimals']
        buy_amount = int(response['toTokenAmount']) / 10 ** response['toToken']['decimals']
        price = buy_amount / sell_amount
        value = '0'
        if sell_token.lower() == config.NATIVE_TOKEN_ADDRESS:
            value = str(sell_amount)
        try:
            sources = self.convert_sources_for_meta_aggregation(response['protocols'])
            res = MetaSwapPriceResponse(
                provider=self._provider_name,
                sources=sources,
                buy_amount=response['toTokenAmount'],
                gas=response['estimatedGas'],
                sell_amount=response['fromTokenAmount'],
                gas_price=gas_price if gas_price else '0',
                value=value,
                price=price,
            )
        except (KeyError, ValidationError) as e:
            e = self.handle_exception(e, response=response, method='_convert_response_from_swap_quote',
                                      price=price, url=url, params=query, chain_id=chain_id)
            raise e
        return res

    async def get_swap_quote(
            self,
            buy_token: str,
            sell_token: str,
            sell_amount: int,
            chain_id: Optional[int] = None,
            affiliate_address: Optional[str] = None,
            gas_price: Optional[int] = None,
            slippage_percentage: Optional[float] = None,
            taker_address: Optional[str] = None,
            fee_recipient: Optional[str] = None,
            buy_token_percentage_fee: Optional[float] = None,
            ignore_checks: bool = False,
    ) -> Optional[SwapQuoteResponse]:
        """https://docs.1inch.io/docs/aggregation-protocol/api/swap-params"""
        if not chain_id:
            raise ValueError('chain_id is required')

        if not slippage_percentage:
            slippage_percentage = DEFAULT_SLIPPAGE_PERCENTAGE
        else:
            slippage_percentage = slippage_percentage * 100  # 1inch awaits slippage in percents
        if not taker_address:
            raise ValueError('Taker address is required')

        path = 'swap'
        url = self._trading_api_path_builder(
            version=TRADING_API_VERSION,
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

        if affiliate_address:
            query['referrerAddress'] = affiliate_address

        if fee_recipient and not affiliate_address:
            query['referrerAddress'] = fee_recipient

        if buy_token_percentage_fee:
            query['fee'] = buy_token_percentage_fee
        query.update(MAX_RESULT_PRESET)
        try:
            response = await self.get_response(url, query)
        except (ClientResponseError, asyncio.TimeoutError, ServerDisconnectedError) as e:
            exc = self.handle_exception(e, params=query, token_address=sell_token, chain_id=chain_id)
            raise exc
        sell_amount = int(sell_amount) / 10 ** response['fromToken']['decimals']
        buy_amount = int(response['toTokenAmount']) / 10 ** response['toToken']['decimals']
        price = buy_amount / sell_amount
        return self._convert_response_from_swap_quote(response, price, url=url, query=query)

    def _convert_response_from_swap_quote(
            self,
            response: dict,
            price: float,
            **kwargs,
    ) -> Optional[SwapQuoteResponse]:
        sources = self.convert_sources_for_meta_aggregation(response['protocols'])
        try:
            prepared_response = SwapQuoteResponse(
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
            e = self.handle_exception(e, response=response, method='_convert_response_from_swap_quote',
                                      price=price, **kwargs)
            raise e
        else:
            return prepared_response

    @staticmethod
    def convert_sources_for_meta_aggregation(
            sources: Optional[dict, list[dict]],
    ) -> Optional[list[SwapSources]]:
        if not sources:
            return
        sources_list = list(chain.from_iterable(chain.from_iterable(sources)))
        converted_sources = []
        for source in sources_list:
            source['name'] = AMM_MAPPING.get(source['name'], source['name'])
            converted_sources.append(SwapSources(name=source['name'], proportion=source['part']))
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
        exc = super().handle_exception(exception, logger, **kwargs)
        if exc:
            return exc
        msg = exception.message
        if isinstance(exception.message, list) and isinstance(exception.message[0], dict):
            msg = exception.message[0].get('description')
        for error, error_class in ONE_INCH_ERRORS.items():
            if re.search(error.lower(), msg.lower()):
                break
        else:
            error_class = AggregationProviderError
        exc = error_class(
            self._provider_name,
            msg,
            url=str(exception.request_info.url),
            **kwargs,
        )
        if isinstance(exc, EstimationError):
            logger.warning(
                f'potentially blacklist. %({LogArgs.token_idx})s',
                {LogArgs.token_idx: f'{kwargs.get("token_address")}-{kwargs.get("chain_id")}'},
                extra={'token_address': kwargs.get('token_address'), 'chain_id': kwargs.get('chain_id')},
            )
        logger.warning(*exc.to_log_args(), extra=exc.to_dict())
        return exc
