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

    BASE_URL: yarl.URL = yarl.URL("api.bebop.xyz")
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

    def _api_path_builder(self, chain_id: int, endpoint: str) -> str:
        network = (
            ""
            if not chain_id or chain_id == self.chains.eth.chain_id
            else f"{self.chains.get_chain_by_id(chain_id).name}."
        )
        return f"{self.BASE_URL}/{network}/v{self.TRADING_API_VERSION}/{endpoint}"

    async def _get_response(self, url: str, params: dict | None = None) -> dict:
        async with self.aiohttp_session.get(
            url, params=params, timeout=self.REQUEST_TIMEOUT, ssl=ssl.SSLContext()
        ) as response:
            logger.debug(f"Request GET {response.url}")
            data: dict = await response.json()
            try:
                response.raise_for_status()
            except aiohttp.ClientResponseError as e:
                status = 500 if e.status not in range(100, 600) else e.status
                data["source"] = "Bebop API Proxy"
                raise aiohttp.ClientResponseError(
                    request_info=e.request_info,
                    history=e.history,
                    status=status,
                    message=str(data),
                    headers=e.headers,
                )

        return data

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
            - https://api.bebop.xyz/ethereum/v2/quote?buy_tokens=0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE&sell_tokens=0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48&sell_amounts=1000000000000000000&taker_address=0x0000000000000000000000000000000000000001&approval_type=Standard&skip_validation=true&gasless=false
        """
        url = self._api_path_builder(chain_id=chain_id, endpoint="quote")
        params = {
            "sell_tokens": sell_token,
            "buy_tokens": buy_token,
            "sell_amounts": sell_amount,
            "buy_amounts": None,
            "source": self.config.PARTNER,
            "taker_address": taker_address
            or "0x0000000000000000000000000000000000000001",
            "approval_type": "Standard",
            "gasless": False,
            "skip_validation": skip_validation,
        }

        try:
            response = await self._get_response(url=url, params=params)
        except Exception:
            raise self.handle_exception(exception=Exception(response))

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
        return []

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
                price=next(iter(response["sellTokens"].values()))["rate"],
                sell_amount=next(iter(response["sellTokens"].values()))["amount"],
                sources=sources,
                to=response["tx"]["to"],
                value=response["tx"]["value"],
            )
        except Exception:
            raise self.handle_exception(Exception(response))
        return prepared_response

    def _convert_response_from_swap_price(
        self, response: dict
    ) -> ProviderPriceResponse:
        try:
            sources = self.convert_sources_for_meta_aggregation()
            prepared_response = ProviderPriceResponse(
                allowance_target=response["tx"]["to"],
                buy_amount=next(iter(response["buyTokens"].values()))["amount"],
                gas_price=response["tx"]["gasPrice"],
                gas=response["tx"]["gas"],
                price=next(iter(response["sellTokens"].values()))["rate"],
                provider=self.PROVIDER_NAME,
                sell_amount=next(iter(response["sellTokens"].values()))["amount"],
                sources=sources,
                value=response["tx"]["value"],
            )
        except Exception:
            raise self.handle_exception(Exception(response))
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
                exc = AggregationProviderError
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
