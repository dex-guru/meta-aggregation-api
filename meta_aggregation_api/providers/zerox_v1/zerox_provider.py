import asyncio
import re
import ssl
from pathlib import Path
from typing import List, Optional, Union

import aiohttp
import ujson
from aiocache import cached
from aiohttp import ClientResponse, ClientResponseError, ServerDisconnectedError
from pydantic import ValidationError

from meta_aggregation_api.clients.apm_client import ApmClient
from meta_aggregation_api.config import Config
from meta_aggregation_api.models.meta_agg_models import (
    ProviderPriceResponse,
    ProviderQuoteResponse,
    SwapSources,
)
from meta_aggregation_api.providers.base_provider import BaseProvider
from meta_aggregation_api.services.chains import ChainsConfig
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
from meta_aggregation_api.utils.logger import get_logger

logger = get_logger(__name__)

ZERO_X_ERRORS = {
    'Insufficient funds for transaction': UserBalanceError,
    'IncompleteTransformERC20Error': TokensError,
    'INSUFFICIENT_ASSET_LIQUIDITY': InsufficientLiquidityError,
    'WalletExecuteDelegateCallFailedError': AggregationProviderError,
    'SenderNotAuthorizedError': AllowanceError,
    'Gas estimation failed': EstimationError,
    'ERC20: insufficient allowance': AllowanceError,
}


# TODO: Add description, links to one 0x docs


class ZeroXProviderV1(BaseProvider):
    """Docs: https://0x.org/docs/api#introduction"""

    API_DOMAIN = 'api.0x.org'
    TRADING_API_VERSION = 1
    with open(Path(__file__).parent / 'config.json') as f:
        PROVIDER_NAME = ujson.load(f)['name']

    def __init__(
        self,
        session: aiohttp.ClientSession,
        config: Config,
        chains: ChainsConfig,
        apm_client: ApmClient,
    ):
        super().__init__(session=session, config=config, apm_client=apm_client)
        self.chains = chains

        self.get_swap_price = cached(
            ttl=30, **get_cache_config(self.config), noself=True
        )(self.get_swap_price)

    def _api_domain_builder(self, chain_id: int = None) -> str:
        network = (
            ''
            if not chain_id or chain_id == self.chains.eth.chain_id
            else f'{self.chains.get_chain_by_id(chain_id).name}.'
        )
        return f'{network}{self.API_DOMAIN}'

    def _api_path_builder(
        self, path: str, endpoint: str, chain_id: Optional[str] = None
    ) -> str:
        domain = self._api_domain_builder(chain_id)
        return f'https://{domain}/{path}/v{self.TRADING_API_VERSION}/{endpoint}'

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
                data['source'] = 'proxied 0x.org API'
                raise ClientResponseError(
                    request_info=e.request_info,
                    history=e.history,
                    status=status,
                    # Hack for error init method: expected str, but list and dict also works.
                    message=[data],
                    headers=e.headers,
                )

        return data

    def _convert_response_from_swap_quote(
        self, response: dict
    ) -> Optional[ProviderQuoteResponse]:
        sources = self.convert_sources_for_meta_aggregation(response['sources'])
        try:
            prepared_response = ProviderQuoteResponse(
                sources=sources,
                buy_amount=response['buyAmount'],
                gas=response['gas'],
                sell_amount=response['sellAmount'],
                to=response['to'],
                data=response['data'],
                gas_price=response['gasPrice'],
                value=response['value'],
                price=response['price'],
            )
        except (KeyError, ValidationError) as e:
            e = self.handle_exception(e, response=response)
            raise e
        else:
            return prepared_response

    @staticmethod
    def convert_sources_for_meta_aggregation(
        sources: Optional[Union[dict, list[dict]]],
    ) -> Optional[list[SwapSources]]:
        if not sources:
            return
        converted_sources = []
        for source in sources:
            if not float(source['proportion']):
                continue
            if source.get('hops'):
                converted_sources.extend(
                    [
                        SwapSources(
                            name=hop, proportion=float(source['proportion']) * 100
                        )
                        for hop in source['hops']
                    ]
                )
                continue
            converted_sources.append(
                SwapSources(
                    name=source['name'],
                    proportion=float(source['proportion']) * 100,
                    # Convert to percentage.
                )
            )
        return converted_sources

    def _convert_response_from_swap_price(
        self, response: dict
    ) -> Optional[ProviderPriceResponse]:
        try:
            sources = self.convert_sources_for_meta_aggregation(response['sources'])
            prepared_response = ProviderPriceResponse(
                provider=self.PROVIDER_NAME,
                sources=sources,
                buy_amount=response['buyAmount'],
                gas=response['gas'],
                sell_amount=response['sellAmount'],
                gas_price=response['gasPrice'],
                value=response['value'],
                price=response['price'],
            )
        except (KeyError, ValidationError) as e:
            e = self.handle_exception(e, response=response)
            raise e
        else:
            return prepared_response

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
        **_,
    ) -> Optional[ProviderQuoteResponse]:
        """
        Docs: https://0x.org/docs/api#get-swapv1quote

        Examples:
            - https://api.0x.org/swap/v1/quote?buyToken=0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE&sellAmount=1000000&sellToken=0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48
            - https://api.0x.org/swap/v1/quote?buyToken=0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48&sellAmount=1000000000000000000&sellToken=0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE
            - https://api.0x.org/swap/v1/quote?affiliateAddress=0x720c9244473Dfc596547c1f7B6261c7112A3dad4&buyToken=0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48&gasPrice=26000000000&sellAmount=1000000000000000000&sellToken=0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE&slippagePercentage=0.0100&takerAddress=0xA0942D8352FFaBCc0f6dEE32b2b081C703e726A5
        """
        url = self._api_path_builder('swap', 'quote', chain_id)
        ignore_checks = str(ignore_checks).lower()
        query = {
            'buyToken': buy_token,
            'sellToken': sell_token,
            'sellAmount': sell_amount,
            'skipValidation': ignore_checks,
        }

        if gas_price:
            query['gasPrice'] = gas_price

        if slippage_percentage:
            query['slippagePercentage'] = slippage_percentage

        if taker_address:
            query['takerAddress'] = taker_address

        if fee_recipient and buy_token_percentage_fee:
            query['feeRecipient'] = fee_recipient
            query['affiliateAddress'] = fee_recipient
            query['buyTokenPercentageFee'] = buy_token_percentage_fee

        logger.debug(f'Proxing url {url} with params {query}')
        try:
            response = await self._get_response(url, params=query)
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ServerDisconnectedError,
        ) as e:
            e = self.handle_exception(
                e, query=query, method='get_swap_quote', chain_id=chain_id
            )
            raise e
        logger.info(f'Got price_response from 0x.org: {response}')
        return self._convert_response_from_swap_quote(response)

    async def get_orders_by_trader(
        self,
        *,
        chain_id: int,
        trader: str,
        maker_token: str = None,
        taker_token: Optional[int] = None,
        statuses: Optional[List] = None,
    ) -> dict:
        """
        Docs: https://docs.0x.org/0x-api-orderbook/introduction

        Examples:
            https://docs.0x.org/0x-api-orderbook/api-references
        """
        url = self._api_path_builder('orderbook', 'orders', str(chain_id))
        query = {}

        if taker_token:
            query['takerToken'] = taker_token

        if maker_token:
            query['makerToken'] = maker_token

        if trader:
            query['trader'] = trader

        logger.debug(f'Proxing url {url} with params {query}')
        return await self._get_response(url, params=query)

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
        **_,
    ) -> Optional[ProviderPriceResponse]:
        """
        Docs: https://0x.org/docs/api#get-swapv1price
        """
        url = self._api_path_builder('swap', 'price', chain_id)
        query = {
            'buyToken': buy_token,
            'sellToken': sell_token,
            'sellAmount': sell_amount,
        }

        if gas_price:
            query['gasPrice'] = gas_price

        if slippage_percentage:
            query['slippagePercentage'] = slippage_percentage

        if taker_address:
            query['takerAddress'] = taker_address

        if fee_recipient and buy_token_percentage_fee:
            query['feeRecipient'] = fee_recipient
            query['affiliateAddress'] = fee_recipient
            query['buyTokenPercentageFee'] = buy_token_percentage_fee

        logger.debug(f'Proxing url {url} with params {query}')
        try:
            response = await self._get_response(url, params=query)
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ServerDisconnectedError,
        ) as e:
            e = self.handle_exception(
                e, query=query, method='get_swap_price', chain_id=chain_id
            )
            raise e
        return self._convert_response_from_swap_price(response) if response else None

    def handle_exception(
        self, exception: Union[ClientResponseError, KeyError, ValidationError], **kwargs
    ) -> BaseAggregationProviderError:
        """
        exception.message: [
            {
                "code": 101,
                "reason": "Validation failed",
                "validationErrors": [
                    {
                        "field": "maker",
                        "code": 1002,
                        "reason": "Invalid address"
                    }
                ]
            }
        ]
        or
        exception.message: [
            {
                "code": 105,
                "reason": "Transaction Invalid",
                "values": {
                    "message": "execution reverted",
                }
            }
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
            msg = exception.message[0]
            if msg.get('validationErrors'):
                msg = {msg['field']: msg['reason'] for msg in msg['validationErrors']}
            else:
                msg = msg.get('values', msg).get('message', msg.get('reason', msg))

        for error, error_class in ZERO_X_ERRORS.items():
            if re.search(error.lower(), str(msg).lower()):
                break
        else:
            error_class = AggregationProviderError
        exc = error_class(
            self.PROVIDER_NAME,
            msg,
            url=str(exception.request_info.url),
            **kwargs,
        )
        logger.warning(*exc.to_log_args(), extra=exc.to_dict())
        return exc
