from __future__ import annotations

import ssl
import aiohttp
from pydantic import BaseModel
import yarl
from meta_aggregation_api.models.meta_agg_models import (
    ProviderPriceResponse,
    ProviderQuoteResponse,
)
from meta_aggregation_api.models.provider_response_models import SwapSources
from meta_aggregation_api.providers.base_provider import BaseProvider
from meta_aggregation_api.utils.logger import get_logger
from meta_aggregation_api.config import Config
from meta_aggregation_api.clients.apm_client import ApmClient
from meta_aggregation_api.services.chains import ChainsConfig
from web3 import Web3

from meta_aggregation_api.utils.errors import (
    BaseAggregationProviderError,
    InsufficientLiquidityError,
    UserBalanceError,
    AllowanceError,
    EstimationError,
    AggregationProviderError,
    TokensError,
    PriceError,
    ProviderTimeoutError,
    ValidationFailedError,
)
from pathlib import Path
import ujson

logger = get_logger(__name__)

BEBOP_ERRORS = {
    # ------------------------------- /quote Errors ------------------------------ #
    101: ValidationFailedError,
    102: InsufficientLiquidityError,
    103: EstimationError,
    104: PriceError,
    105: TokensError,
    106: PriceError,
    107: AggregationProviderError,
    # ------------------------------- /order Errors ------------------------------ #
    201: AggregationProviderError,
    202: AggregationProviderError,
    203: AggregationProviderError,
    204: UserBalanceError,
    205: AllowanceError,
    206: AggregationProviderError,
    207: AggregationProviderError,
    208: AggregationProviderError,
    209: AggregationProviderError,
    210: AggregationProviderError,
    211: AggregationProviderError,
    212: AggregationProviderError,
    500: AggregationProviderError,
    522: ProviderTimeoutError,
}


class BebopError(BaseModel):
    error_code: int
    message: str

    @staticmethod
    def from_json(json: dict) -> BebopError:
        return BebopError(
            error_code=json["error"]["errorCode"], message=json["error"]["message"]
        )


class BebopProviderV2(BaseProvider):
    """Docs: https://docs.bebop.xyz"""

    BASE_URL: yarl.URL = yarl.URL("https://api.bebop.xyz")
    TRADING_API_VERSION: int = 2

    with open(Path(__file__).parent / "config.json") as f:
        PROVIDER_NAME = ujson.load(f)["name"]

    def __init__(
        self,
        session: aiohttp.ClientSession,
        config: Config,
        chains: ChainsConfig,
        apm_client: ApmClient,
    ):
        super().__init__(session=session, config=config, apm_client=apm_client)
        self.chains = chains
        self.api_key = self.config.BEBOP_API_KEY

    def _api_path_builder(self, chain_id: int, endpoint: str) -> yarl.URL:
        network = (
            "ethereum"
            if not chain_id or chain_id == self.chains.eth.chain_id
            else f"{self.chains.get_chain_by_id(chain_id).name}"
        )
        return self.BASE_URL / network / f"v{self.TRADING_API_VERSION}" / endpoint

    async def _get_response(self, url: str, params: dict | None = None) -> dict:
        headers = {
            "Source-Auth": self.api_key
        }
        async with self.aiohttp_session.get(
            url, params=params, timeout=self.REQUEST_TIMEOUT, headers=headers, ssl=ssl.SSLContext()
        ) as response:
            logger.debug(f"Request GET {response.url}")
            logger.debug(f"Request headers {response.request_info.headers}")
            data = await response.read()
            if not data:
                return {}
            try:
                data_json: dict = ujson.loads(data)
                logger.debug("Response Body {data_json}")
            except ValueError:
                raise Exception(data.decode("utf-8"))
            # Handle status 200 error response
            if data_json.get("error"):
                raise Exception(data_json)
            try:
                response.raise_for_status()
            except aiohttp.ClientResponseError as e:
                status = 500 if e.status not in range(100, 600) else e.status
                data_json["source"] = "Bebop API Proxy"
                raise aiohttp.ClientResponseError(
                    request_info=e.request_info,
                    history=e.history,
                    status=status,
                    message=str(data),
                    headers=e.headers,
                )

        return data_json

    async def __get_price(
        self,
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        chain_id: int,
        skip_validation: bool,
        taker_address: str | None = None,
    ) -> dict:
        """
        Docs: https://api.bebop.xyz/docs#/v2/v2_quote_v2_quote_get

        Examples:
            - https://api.bebop.xyz/ethereum/v2/quote?buy_tokens=0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE&sell_tokens=0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48&sell_amounts=100000000&taker_address=0x0000000000000000000000000000000000000001&approval_type=Standard&skip_validation=true&gasless=false
        """
        url = self._api_path_builder(chain_id=chain_id, endpoint="quote")
        params = {
            "sell_tokens": Web3.toChecksumAddress(sell_token),
            "buy_tokens": Web3.toChecksumAddress(buy_token),
            "sell_amounts": sell_amount,
            "source": self.config.PARTNER,
            "taker_address": Web3.toChecksumAddress(taker_address)
            if taker_address
            else "0x0000000000000000000000000000000000000001",
            "approval_type": "Standard",
            "gasless": 0,
            "skip_validation": int(skip_validation),
        }

        try:
            response = await self._get_response(url=str(url), params=params)
        except Exception as e:
            self.handle_exception(exception=e, **params)
            raise e

        logger.info(f"Bebop response: {response}")
        return response

    async def get_swap_price(
        self,
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        chain_id: int,
        gas_price: int | None = None,
        slippage_percentage: float | None = None,
        taker_address: str | None = None,
        fee_recipient: str | None = None,
        buy_token_percentage_fee: float | None = None,
        **_,
    ) -> ProviderPriceResponse:
        response = await self.__get_price(
            buy_token=buy_token,
            sell_token=sell_token,
            sell_amount=sell_amount,
            chain_id=chain_id,
            taker_address=taker_address,
            skip_validation=True,
        )
        return self._convert_response_from_swap_price(response)

    async def get_swap_quote(
        self,
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        chain_id: int,
        taker_address: str,
        gas_price: int | None = None,
        slippage_percentage: float | None = 0,
        fee_recipient: str | None = None,
        buy_token_percentage_fee: float | None = None,
    ) -> ProviderQuoteResponse:
        response = await self.__get_price(
            buy_token=buy_token,
            sell_token=sell_token,
            sell_amount=sell_amount,
            chain_id=chain_id,
            taker_address=taker_address,
            skip_validation=False,
        )
        return self._convert_response_from_swap_quote(response)

    @staticmethod
    def convert_sources_for_meta_aggregation(
        sources: dict | list[dict] | None = None,
    ) -> list[SwapSources]:
        return [SwapSources(name="bebop", proportion=100)]

    def _convert_response_from_swap_quote(
        self,
        response: dict,
    ) -> ProviderQuoteResponse:
        sources = self.convert_sources_for_meta_aggregation()
        try:
            prepared_response = ProviderQuoteResponse(
                buy_amount=next(iter(response["buyTokens"].values()))["amount"],
                data=response["tx"]["data"],
                gas_price=response["tx"]["gasPrice"],
                gas=response["tx"]["gas"],
                price=next(iter(response["sellTokens"].values()))["price"],
                sell_amount=next(iter(response["sellTokens"].values()))["amount"],
                sources=sources,
                to=response["tx"]["to"],
                value=response["tx"]["value"],
            )
        except Exception as e:
            raise self.handle_exception(e)
        return prepared_response

    def _convert_response_from_swap_price(
        self, response: dict
    ) -> ProviderPriceResponse:
        try:
            sources = self.convert_sources_for_meta_aggregation()
            prepared_response = ProviderPriceResponse(
                allowance_target=response["tx"]["to"],
                buy_amount=next(iter(response["buyTokens"].values()))["amountBeforeFee"],
                gas_price=response["tx"]["gasPrice"],
                gas=response["tx"]["gas"],
                price=next(iter(response["sellTokens"].values()))["priceBeforeFee"],
                provider=self.PROVIDER_NAME,
                sell_amount=next(iter(response["sellTokens"].values()))["amount"],
                sources=sources,
                value=response["tx"]["value"],
            )
        except Exception as e:
            raise self.handle_exception(e)
        else:
            return prepared_response

    def handle_exception(
        self,
        exception: Exception,
        **kwargs,
    ) -> BaseAggregationProviderError:
        """
        exception.message:
        {
            "error": {
                "errorCode": 102,
                "message": "InsufficientLiquidity: Insufficient liquidity for pairs
                            ['USDC/WETH']"
            }
        }
        """
        msg: dict = exception.args[0]

        if "error" not in msg:
            if exc := super().handle_exception(exception, **kwargs):
                exc = exc
            else:
                exc = AggregationProviderError(
                    self.PROVIDER_NAME, str(exception), **kwargs
                )
            logger.error(*exc.to_log_args(), extra=exc.to_dict())
            return exc

        bebop_error: BebopError = BebopError.from_json(json=msg)
        if err := BEBOP_ERRORS.get(int(bebop_error.error_code)):
            error_class = err
        else:
            error_class = AggregationProviderError

        exc = error_class(
            provider=self.PROVIDER_NAME,
            message=bebop_error.message,
        )

        logger.warning(*exc.to_log_args(), extra=exc.to_dict())
        return exc
