import asyncio
import logging
import re
import ssl
from decimal import Decimal
from itertools import chain
from typing import Optional, Union

import ujson
import yarl
from aiohttp import ClientResponseError, ServerDisconnectedError
from pydantic import ValidationError
from tenacity import retry, stop_after_attempt, retry_if_exception_type, before_log

from config import config
from models.meta_agg_models import SwapQuoteResponse, MetaSwapPriceResponse
from models.provider_response_models import SwapSources
from provider_clients.base_provider import BaseProvider
from utils.errors import AggregationProviderError, EstimationError, UserBalanceError, TokensError, PriceError, \
    AllowanceError, ValidationFailedError, BaseAggregationProviderError
from utils.logger import get_logger, LogArgs

logger = get_logger(__name__)

PARASWAP_ERRORS = {
    # ---- price errors
    'Invalid tokens': TokensError,
    'Token not found': TokensError,
    'Price Timeout': PriceError,
    'computePrice Error': PriceError,
    'Bad USD price': PriceError,
    'ERROR_GETTING_PRICES': PriceError,
    # ---- quote errors
    'Unable to check price impact': PriceError,
    'not enough \w+ balance': UserBalanceError,
    'not enough \w+ allowance': AllowanceError,
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


# TODO: Add description, links to one paraswap docs


class ParaSwapProvider(BaseProvider):
    MAIN_API_URL: yarl.URL = yarl.URL("https://apiv5.paraswap.io/")
    PARTNER: str = "DexGuru"
    _provider_name = 'paraswap'

    @retry(retry=(retry_if_exception_type(asyncio.TimeoutError) | retry_if_exception_type(ServerDisconnectedError)),
           stop=stop_after_attempt(3), reraise=True, before=before_log(logger, logging.DEBUG))
    async def request(self, method: str, path: str, *args, **kwargs):
        request_function = getattr(self.aiohttp_session, method.lower())
        url = self.MAIN_API_URL / path
        async with request_function(url, *args, timeout=5, **kwargs, ssl=ssl.SSLContext()) as response:
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
            affiliate_address: Optional[str] = None,
            gas_price: Optional[int] = None,
            slippage_percentage: Optional[float] = None,
            taker_address: Optional[str] = None,
            fee_recipient: Optional[str] = None,
            buy_token_percentage_fee: Optional[float] = None,
    ):
        path = 'prices'
        params = {
            "srcToken": sell_token,
            "destToken": buy_token,
            "amount": sell_amount,
            "side": "SELL",
            "network": chain_id,
            "otherExchangePrices": 'false',
            'partner': self.PARTNER,
        }

        try:
            quotes = await self.request(method="get", path=path, params=params)
        except (ClientResponseError, asyncio.TimeoutError, ServerDisconnectedError, Exception) as e:
            e = self.handle_exception(e, method='get_swap_price', params=params, chain_id=chain_id)
            raise e
        response = self._convert_response_from_swap_price(quotes)
        response.gasPrice = gas_price or 0
        if sell_token.lower() == config.NATIVE_TOKEN_ADDRESS:
            response.value = str(sell_amount)
        return response

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
        params = {
            "srcToken": sell_token,
            "destToken": buy_token,
            "amount": sell_amount,
            "side": "SELL",
            "network": chain_id,
            "otherExchangePrices": 'false',
            'partner': self.PARTNER,
        }
        if taker_address:
            params["userAddress"] = taker_address
        try:
            response = await self.request(method="get", path="prices", params=params)
        except (ClientResponseError, asyncio.TimeoutError, ServerDisconnectedError) as e:
            e = self.handle_exception(e, method='get_swap_quote', params=params, chain_id=chain_id)
            raise e

        price_route = response["priceRoute"]
        ignore_checks = str(ignore_checks).lower()
        params = {"network": price_route["network"], 'ignoreChecks': ignore_checks}
        if gas_price is not None:
            params["gasPrice"] = gas_price
        data = {
            "srcToken": sell_token,
            "destToken": buy_token,
            "srcAmount": str(sell_amount),
            "priceRoute": price_route,
            "userAddress": taker_address,
            "partner": self.PARTNER,
            "srcDecimals": price_route["srcDecimals"],
            "destDecimals": price_route["destDecimals"],
        }

        if buy_token_percentage_fee:
            data['partnerFeeBps'] = int(buy_token_percentage_fee * 10000)  # 100% -> 10000
        if slippage_percentage:
            data['slippage'] = int(slippage_percentage * 10000)  # 100% -> 10000
        else:
            data["destAmount"] = str(price_route["destAmount"]),

        if affiliate_address or fee_recipient:
            data['partnerAddress'] = affiliate_address or fee_recipient

        try:
            response = await self.request(
                method="post",
                path=f"transactions/{price_route['network']}",
                params=params,
                json=data,
            )
        except (ClientResponseError, asyncio.TimeoutError, ServerDisconnectedError) as e:
            e = self.handle_exception(e, response=response, data=data, params=params, chain_id=chain_id)
            raise e
        return self._convert_response_from_swap_quote(response, price_route)

    def _convert_response_from_swap_quote(
            self,
            quote_response: dict,
            price_response: dict,
            **kwargs,
    ) -> Optional[SwapQuoteResponse]:
        price = Decimal(price_response['destAmount']) / Decimal(price_response['srcAmount'])
        sources = self.convert_sources_for_meta_aggregation(price_response['bestRoute'])
        try:
            prepared_response = SwapQuoteResponse(
                sources=sources,
                buy_amount=str(price_response["destAmount"]),
                gas=quote_response.get("gas", '0'),
                sell_amount=price_response["srcAmount"],
                to=quote_response['to'],
                data=quote_response['data'],
                gas_price=quote_response['gasPrice'],
                value=quote_response['value'],
                price=str(price),
            )
        except (KeyError, ValidationError) as e:
            e = self.handle_exception(e, response=quote_response, method='_convert_response_from_swap_quote',
                                      price_response=price, **kwargs)
            raise e
        return prepared_response

    def _convert_response_from_swap_price(self, price_response: dict) -> Optional[MetaSwapPriceResponse]:
        price_response = price_response['priceRoute']
        dst_amount = (Decimal(price_response['destAmount']) / 10 ** price_response['destDecimals'])
        src_amount = (Decimal(price_response['srcAmount']) / 10 ** price_response['srcDecimals'])
        price = dst_amount / src_amount
        sources = self.convert_sources_for_meta_aggregation(price_response['bestRoute'])
        try:
            prepared_response = MetaSwapPriceResponse(
                provider=self._provider_name,
                sources=sources,
                buy_amount=str(price_response["destAmount"]),
                gas=price_response['gasCost'],
                sell_amount=price_response["srcAmount"],
                gas_price='0',
                value='0',
                price=str(price),
            )
        except (KeyError, ValidationError) as e:
            e = self.handle_exception(e, response=price_response, method='_convert_response_from_swap_price')
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
            converted_sources.append(SwapSources(name=source['exchange'], proportion=source['percent']))
        return converted_sources

    def handle_exception(self, exception: Union[ClientResponseError, KeyError, ValidationError],
                         **kwargs) -> BaseAggregationProviderError:
        """
        exception.message: "{"error": "Not enough liquidity for this trade"}"
        """
        exc = super().handle_exception(exception, logger, **kwargs)
        if exc:
            return exc
        msg = ujson.loads(exception.message).get('error', 'Unknown error')
        for error, error_class in PARASWAP_ERRORS.items():
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
                f'potentially blacklist. %({LogArgs.token_idx})',
                {LogArgs.token_idx: f'{kwargs.get("token_address")}-{kwargs.get("chain_id")}'},
                extra={'token_address': kwargs.get('token_address'), 'chain_id': kwargs.get('chain_id')},
            )
        logger.warning(*exc.to_log_args(), extra=exc.to_dict())
        return exc
