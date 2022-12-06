import asyncio
import logging
import re
import ssl
from typing import Union, Optional, List

from aiohttp import ClientResponseError, ClientResponse, ServerDisconnectedError
from pydantic import ValidationError
from tenacity import retry, stop_after_attempt, retry_if_exception_type, before_log

from config.chains import chains
from models.meta_agg_models import SwapQuoteResponse, SwapSources
from models.provider_response_models import SwapPriceResponse
from provider_clients.base_provider import BaseProvider
from utils.errors import AggregationProviderError, UserBalanceError, BaseAggregationProviderError
from utils.logger import get_logger

logger = get_logger(__name__)

ZERO_X_ERRORS = {
    'Insufficient funds for transaction': UserBalanceError,
    # TODO add more errors
}

# TODO: Add description, links to one 0x docs


class ZeroXProvider(BaseProvider):
    """ Docs: https://0x.org/docs/api#introduction """
    api_domain = 'api.0x.org'
    _provider_name = 'zero_x'
    supported_chains = (1, 56)

    @classmethod
    def _api_domain_builder(cls, chain_id: int = None) -> str:
        network = '' if not chain_id or chain_id == chains.eth.chain_id else f'{chains.get_chain_by_id(chain_id).name}.'
        return f'{network}{cls.api_domain}'

    @classmethod
    def _api_path_builder(
            cls,
            path: str,
            version: Union[int, float],
            endpoint: str,
            chain_id: Optional[str] = None
    ) -> str:
        domain = cls._api_domain_builder(chain_id)
        return f'https://{domain}/{path}/v{version}/{endpoint}'

    @retry(retry=(retry_if_exception_type(asyncio.TimeoutError) | retry_if_exception_type(ServerDisconnectedError)),
           stop=stop_after_attempt(3), reraise=True, before=before_log(logger, logging.DEBUG))
    async def _get_response(self, url: str, params: Optional[dict] = None) -> dict:
        async with self.aiohttp_session.get(url, params=params, timeout=5, ssl=ssl.SSLContext()) as response:
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
                    headers=e.headers
                )

        return data

    def _convert_response_from_swap_quote(self, response: dict) -> Optional[SwapQuoteResponse]:
        try:
            prepared_response = SwapQuoteResponse(
                sources=response['sources'],
                buyAmount=response['buyAmount'],
                gas=response['gas'],
                sellAmount=response['sellAmount'],
                to=response['to'],
                data=response['data'],
                gasPrice=response['gasPrice'],
                value=response['value'],
                price=response['price'],
            )
        except (KeyError, ValidationError) as e:
            e = self.handle_exception(e, response=response)
            raise e
        else:
            return self.convert_sources_for_meta_aggregation(prepared_response)

    @staticmethod
    def convert_sources_for_meta_aggregation(
            quote: Optional[Union[SwapPriceResponse, SwapQuoteResponse]],
    ) -> Optional[Union[SwapPriceResponse, SwapQuoteResponse]]:
        if not quote:
            return
        sources = []
        for source in quote.sources:
            if not float(source['proportion']):
                continue
            if source.get('hops'):
                source['hops'] = [hop['name'] for hop in source['hops']]
            sources.append(
                SwapSources(
                    name=source['name'],
                    proportion=float(source['proportion']) * 100,  # Convert to percentage.
                    hops=source['hops'] if source.get('hops') else [],
                )
            )
        quote.sources = sources
        return quote

    def _convert_response_from_swap_price(self, response: dict) -> Optional[SwapPriceResponse]:
        try:
            prepared_response = SwapPriceResponse(
                provider=self._provider_name,
                sources=response['sources'],
                buyAmount=response['buyAmount'],
                gas=response['gas'],
                sellAmount=response['sellAmount'],
                gasPrice=response['gasPrice'],
                value=response['value'],
                price=response['price']
            )
        except (KeyError, ValidationError) as e:
            e = self.handle_exception(e, response=response)
            raise e
        else:
            return self.convert_sources_for_meta_aggregation(prepared_response)

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
        """
        Docs: https://0x.org/docs/api#get-swapv1quote

        Examples:
            - https://api.0x.org/swap/v1/quote?buyToken=0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE&sellAmount=1000000&sellToken=0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48
            - https://api.0x.org/swap/v1/quote?buyToken=0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48&sellAmount=1000000000000000000&sellToken=0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE
            - https://api.0x.org/swap/v1/quote?affiliateAddress=0x720c9244473Dfc596547c1f7B6261c7112A3dad4&buyToken=0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48&gasPrice=26000000000&sellAmount=1000000000000000000&sellToken=0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE&slippagePercentage=0.0100&takerAddress=0xA0942D8352FFaBCc0f6dEE32b2b081C703e726A5
        """
        url = self._api_path_builder('swap', 1, 'quote', chain_id)
        ignore_checks = str(ignore_checks).lower()
        query = {
            'buyToken': buy_token,
            'sellToken': sell_token,
            'sellAmount': sell_amount,
            'skipValidation': ignore_checks,
        }

        if affiliate_address:
            query['affiliateAddress'] = affiliate_address

        if gas_price:
            query['gasPrice'] = gas_price

        if slippage_percentage:
            query['slippagePercentage'] = slippage_percentage

        if taker_address:
            query['takerAddress'] = taker_address

        if fee_recipient and buy_token_percentage_fee:
            query['feeRecipient'] = fee_recipient
            query['buyTokenPercentageFee'] = buy_token_percentage_fee

        logger.debug(f'Proxing url {url} with params {query}')
        try:
            response = await self._get_response(url, params=query)
        except (ClientResponseError, asyncio.TimeoutError, ServerDisconnectedError) as e:
            e = self.handle_exception(e, query=query, method='get_swap_quote', chain_id=chain_id)
            raise e
        logger.info(f'Got quote from 0x.org: {response}')
        return self._convert_response_from_swap_quote(response)

    async def get_orders_by_trader(
            self,
            taker_token: str,
            maker_token: str,
            trader: str,
            chain_id: Optional[int] = None,
            statuses: Optional[List] = None,
    ) -> dict:
        """
        Docs: https://docs.0x.org/0x-api-orderbook/introduction

        Examples:
            https://docs.0x.org/0x-api-orderbook/api-references
        """
        url = self._api_path_builder('orderbook', 1, 'orders', chain_id)
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
            affiliate_address: Optional[str] = None,
            gas_price: Optional[int] = None,
            slippage_percentage: Optional[float] = None,
            taker_address: Optional[str] = None,
            fee_recipient: Optional[str] = None,
            buy_token_percentage_fee: Optional[float] = None
    ) -> Optional[SwapPriceResponse]:
        """
        Docs: https://0x.org/docs/api#get-swapv1price
        """
        url = self._api_path_builder('swap', 1, 'price', chain_id)
        query = {
            'buyToken': buy_token,
            'sellToken': sell_token,
            'sellAmount': sell_amount
        }

        if affiliate_address:
            query['affiliateAddress'] = affiliate_address

        if gas_price:
            query['gasPrice'] = gas_price

        if slippage_percentage:
            query['slippagePercentage'] = slippage_percentage

        if taker_address:
            query['takerAddress'] = taker_address

        if fee_recipient and buy_token_percentage_fee:
            query['feeRecipient'] = fee_recipient
            query['buyTokenPercentageFee'] = buy_token_percentage_fee

        logger.debug(f'Proxing url {url} with params {query}')
        try:
            response = await self._get_response(url, params=query)
        except (ClientResponseError, asyncio.TimeoutError, ServerDisconnectedError) as e:
            e = self.handle_exception(e, query=query, method='get_swap_price', chain_id=chain_id)
            raise e
        return self._convert_response_from_swap_price(response) if response else None

    async def get_gas_prices(self, chain_id: Optional[int] = None) -> dict:
        domain = self._api_domain_builder(chain_id)
        url = f'https://gas.{domain}'

        return await self._get_response(url)

    def handle_exception(self, exception: Union[ClientResponseError, KeyError, ValidationError],
                         **kwargs) -> BaseAggregationProviderError:
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
        exc = super().handle_exception(exception, logger, **kwargs)
        if exc:
            return exc
        msg = exception.message
        if isinstance(exception.message, list) and isinstance(exception.message[0], dict):
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
            self._provider_name,
            msg,
            url=str(exception.request_info.url),
            **kwargs,
        )
        logger.warning(*exc.to_log_args(), extra=exc.to_dict())
        return exc
