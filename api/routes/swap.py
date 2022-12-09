from typing import Optional, List

from aiohttp import ClientResponseError
from fastapi import APIRouter, Query, Path, HTTPException
from pydantic import constr, conint

from models.meta_agg_models import MetaPriceModel
from models.meta_agg_models import SwapQuoteResponse
from service.meta_aggregation_service import get_swap_meta_price, get_meta_swap_quote, get_provider_price
from utils.errors import BaseAggregationProviderError, responses

swap_route = APIRouter()
address_to_lower = constr(strip_whitespace=True, min_length=42, max_length=42, to_lower=True)


@swap_route.get('/{chain_id}/price', response_model=MetaPriceModel, responses=responses)
@swap_route.get('/{chain_id}/price/', response_model=MetaPriceModel, include_in_schema=False)
async def get_swap_price(
        buy_token: address_to_lower = Query(..., alias='buyToken'),
        sell_token: address_to_lower = Query(..., alias='sellToken'),
        sell_amount: conint(gt=0) = Query(..., alias='sellAmount'),
        chain_id: int = Path(..., description='Chain ID'),
        gas_price: Optional[int] = Query(None, description='Gas price', gt=0, alias='gasPrice'),
        slippage_percentage: Optional[float] = Query(0.005, gte=0, alias='slippagePercentage'),
        taker_address: Optional[address_to_lower] = Query(None, alias='takerAddress'),
        fee_recipient: Optional[address_to_lower] = Query(None, alias='feeRecipient'),
        buy_token_percentage_fee: Optional[float] = Query(None, alias='buyTokenPercentageFee'),
        provider: Optional[str] = Query(None, alias='provider'),
) -> MetaPriceModel:
    """
    Price endpoints are used to get the best price for a swap. It does not return data for swap and therefore
    require any approvals. If you want to get data for swap, use /price_response endpoint.

    - **buy_token**: Address of the token to buy
    - **sell_token**: Address of the token to sell
    - **sell_amount**: Amount of the token to sell in base units (e.g. 1 ETH = 10**18)
    - **chain_id**: Chain ID. See /info for supported chains
    - **gas_price**: Gas price in wei (optional)
    - **slippage_percentage**: Slippage percentage  (0.01 = 1%) (default: 0.005)
    - **taker_address**: Address of the taker (optional)
    - **fee_recipient**: Address of the fee recipient (optional)
    - **buy_token_percentage_fee**: Percentage of the buy token fee (optional) (0.01 = 1%)
    - **provider**: Provider name from /info (optional). If not specified, the best price will be returned
    """
    params = {
        "buy_token": buy_token,
        "sell_token": sell_token,
        "sell_amount": sell_amount,
        "chain_id": chain_id,
        "gas_price": gas_price,
        "slippage_percentage": slippage_percentage,
        "taker_address": taker_address,
        "fee_recipient": fee_recipient,
        "buy_token_percentage_fee": buy_token_percentage_fee,
    }
    try:
        if provider:
            res = await get_provider_price(provider=provider, **params)
            return res
        else:
            res = await get_swap_meta_price(**params)
    except ClientResponseError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except BaseAggregationProviderError as e:
        raise e.to_http_exception()
    return next((quote for quote in res if quote.is_best), None)


@swap_route.get('/{chain_id}/price/all', response_model=List[MetaPriceModel], responses=responses)
@swap_route.get('/{chain_id}/price/all/', include_in_schema=False, response_model=List[MetaPriceModel])
async def get_all_swap_prices(
        buy_token: address_to_lower = Query(..., alias='buyToken'),
        sell_token: address_to_lower = Query(..., alias='sellToken'),
        sell_amount: conint(gt=0) = Query(..., alias='sellAmount'),
        chain_id: int = Path(..., description='Chain ID'),
        gas_price: Optional[int] = Query(None, description='Gas price', gt=0, alias='gasPrice'),
        slippage_percentage: Optional[float] = Query(0.005, alias='slippagePercentage'),
        taker_address: Optional[address_to_lower] = Query(None, alias='takerAddress'),
        fee_recipient: Optional[address_to_lower] = Query(None, alias='feeRecipient'),
        buy_token_percentage_fee: Optional[float] = Query(None, alias='buyTokenPercentageFee'),
) -> List[MetaPriceModel]:
    """
    Works the same as /price endpoint, but returns all prices from all supported providers.

    - **buy_token**: Address of the token to buy
    - **sell_token**: Address of the token to sell
    - **sell_amount**: Amount of the token to sell in base units (e.g. 1 ETH = 10**18)
    - **chain_id**: Chain ID. See /info for supported chains
    - **gas_price**: Gas price in wei (optional)
    - **slippage_percentage**: Slippage percentage  (0.01 = 1%) (default: 0.005)
    - **taker_address**: Address of the taker (optional)
    - **fee_recipient**: Address of the fee recipient (optional)
    - **buy_token_percentage_fee**: Percentage of the buy token fee (optional) (0.01 = 1%)
    """
    params = {
        "buy_token": buy_token,
        "sell_token": sell_token,
        "sell_amount": sell_amount,
        "chain_id": chain_id,
        "gas_price": gas_price,
        "slippage_percentage": slippage_percentage,
        "taker_address": taker_address,
        "fee_recipient": fee_recipient,
        "buy_token_percentage_fee": buy_token_percentage_fee,
    }

    try:
        res = await get_swap_meta_price(**params)
    except ClientResponseError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except BaseAggregationProviderError as e:
        raise e.to_http_exception()
    return res


@swap_route.get('/{chain_id}/quote', response_model=SwapQuoteResponse, responses=responses)
@swap_route.get('/{chain_id}/quote/', response_model=SwapQuoteResponse, include_in_schema=False)
async def get_swap_quote(
        buy_token: address_to_lower = Query(..., alias='buyToken'),
        sell_token: address_to_lower = Query(..., alias='sellToken'),
        sell_amount: conint(gt=0) = Query(..., alias='sellAmount'),
        chain_id: int = Path(..., description='Chain ID'),
        provider: str = Query(..., alias='provider'),
        gas_price: Optional[int] = Query(None, description='Gas price', gt=0, alias='gasPrice'),
        slippage_percentage: Optional[float] = Query(None, alias='slippagePercentage'),
        taker_address: Optional[address_to_lower] = Query(None, alias='takerAddress'),
        fee_recipient: Optional[address_to_lower] = Query(None, alias='feeRecipient'),
        buy_token_percentage_fee: Optional[float] = Query(None, alias='buyTokenPercentageFee'),
) -> SwapQuoteResponse:
    """
    Returns a data for swap from a specific provider.

    - **buy_token**:Address of the token to buy
    - **sell_token**:Address of the token to sell
    - **sell_amount**:Amount of the token to sell in base units (e.g. 1 ETH = 10**18)
    - **chain_id**: Chain ID. See /info for supported chains
    - **provider**: Provider name from /info
    - **gas_price**: Gas price in wei (optional)
    - **slippage_percentage**: Slippage percentage  (0.01 = 1%) (default: 0.005)
    - **taker_address**: Address of the taker (optional)
    - **fee_recipient**: Address of the fee recipient (optional)
    - **buy_token_percentage_fee**: Percentage of the buy token fee (optional) (0.01 = 1%)
    """
    try:
        quote = await get_meta_swap_quote(
            buy_token=buy_token,
            sell_token=sell_token,
            sell_amount=sell_amount,
            chain_id=chain_id,
            provider=provider,
            gas_price=gas_price,
            slippage_percentage=slippage_percentage,
            taker_address=taker_address,
            fee_recipient=fee_recipient,
            buy_token_percentage_fee=buy_token_percentage_fee,
        )
    except ClientResponseError as e:
        raise HTTPException(status_code=e.status, detail=e.message)
    except BaseAggregationProviderError as e:
        raise e.to_http_exception()
    return quote
