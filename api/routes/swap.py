from typing import Optional, List

from aiohttp import ClientResponseError
from fastapi import APIRouter, Query, Path, HTTPException
from pydantic import constr, conint

from models.meta_agg_models import MetaPriceModel
from models.meta_agg_models import SwapQuoteResponse
from service.meta_aggregation_service import get_swap_meta_price, get_meta_swap_quote, get_provider_price
from utils.errors import BaseAggregationProviderError

swap_route = APIRouter()
address_to_lower = constr(strip_whitespace=True, min_length=42, max_length=42, to_lower=True)


@swap_route.get('/{chain_id}/price', response_model=MetaPriceModel)
@swap_route.get('/{chain_id}/price/', response_model=MetaPriceModel, include_in_schema=False)
async def get_swap_price(
        buy_token: address_to_lower = Query(..., alias='buyToken'),
        sell_token: address_to_lower = Query(..., alias='sellToken'),
        sell_amount: conint(gt=0) = Query(..., alias='sellAmount'),
        chain_id: int = Path(..., description='Chain ID'),
        affiliate_address: Optional[address_to_lower] = Query(None, alias='affiliateAddress'),
        gas_price: Optional[int] = Query(None, description='Gas price', gt=0, alias='gasPrice'),
        slippage_percentage: Optional[float] = Query(None, alias='slippagePercentage'),
        taker_address: Optional[address_to_lower] = Query(None, alias='takerAddress'),
        fee_recipient: Optional[address_to_lower] = Query(None, alias='feeRecipient'),
        buy_token_percentage_fee: Optional[float] = Query(None, alias='buyTokenPercentageFee'),
        provider: Optional[str] = Query(None, alias='provider'),
) -> MetaPriceModel:
    params = {
        "buy_token": buy_token,
        "sell_token": sell_token,
        "sell_amount": sell_amount,
        "chain_id": chain_id,
        "affiliate_address": affiliate_address,
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


@swap_route.get('/{chain_id}/price/all')
@swap_route.get('/{chain_id}/price/all/', include_in_schema=False)
async def get_swap_price(
        buy_token: address_to_lower = Query(..., alias='buyToken'),
        sell_token: address_to_lower = Query(..., alias='sellToken'),
        sell_amount: conint(gt=0) = Query(..., alias='sellAmount'),
        chain_id: int = Path(..., description='Chain ID'),
        affiliate_address: Optional[address_to_lower] = Query(None, alias='affiliateAddress'),
        gas_price: Optional[int] = Query(None, description='Gas price', gt=0, alias='gasPrice'),
        slippage_percentage: Optional[float] = Query(None, alias='slippagePercentage'),
        taker_address: Optional[address_to_lower] = Query(None, alias='takerAddress'),
        fee_recipient: Optional[address_to_lower] = Query(None, alias='feeRecipient'),
        buy_token_percentage_fee: Optional[float] = Query(None, alias='buyTokenPercentageFee'),
) -> List[MetaPriceModel]:
    params = {
        "buy_token": buy_token,
        "sell_token": sell_token,
        "sell_amount": sell_amount,
        "chain_id": chain_id,
        "affiliate_address": affiliate_address,
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


@swap_route.get('/{chain_id}/quote', response_model=SwapQuoteResponse)
@swap_route.get('/{chain_id}/quote/', response_model=SwapQuoteResponse, include_in_schema=False)
async def get_swap_quote(
        buy_token: address_to_lower = Query(..., alias='buyToken'),
        sell_token: address_to_lower = Query(..., alias='sellToken'),
        sell_amount: conint(gt=0) = Query(..., alias='sellAmount'),
        chain_id: int = Path(..., description='Chain ID'),
        provider: str = Query(..., alias='provider'),
        affiliate_address: Optional[address_to_lower] = Query(None, alias='affiliateAddress'),
        gas_price: Optional[int] = Query(None, description='Gas price', gt=0, alias='gasPrice'),
        slippage_percentage: Optional[float] = Query(None, alias='slippagePercentage'),
        taker_address: Optional[address_to_lower] = Query(None, alias='takerAddress'),
        fee_recipient: Optional[address_to_lower] = Query(None, alias='feeRecipient'),
        buy_token_percentage_fee: Optional[float] = Query(None, alias='buyTokenPercentageFee'),
) -> SwapQuoteResponse:
    try:
        quote = await get_meta_swap_quote(
            buy_token=buy_token,
            sell_token=sell_token,
            sell_amount=sell_amount,
            chain_id=chain_id,
            provider=provider,
            affiliate_address=affiliate_address,
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
