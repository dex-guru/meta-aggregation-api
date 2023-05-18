from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import ClientResponseError, RequestInfo

from meta_aggregation_api.models.meta_agg_models import ProviderQuoteResponse
from meta_aggregation_api.providers.one_inch_v5.one_inch_provider import (
    LIMIT_ORDER_VERSION,
)
from meta_aggregation_api.utils.errors import AllowanceError, ParseResponseError


def test_build_limit_order_url(one_inch_provider):
    version = 1
    path = 'test_path'
    endpoint = 'test_endpoint'
    chain_id = 123
    url = one_inch_provider._limit_order_path_builder(
        version=version,
        endpoint=endpoint,
        path=path,
        chain_id=chain_id,
    )
    assert (
        str(url)
        == f'https://{one_inch_provider.LIMIT_ORDERS_DOMAIN}/v{version}/{chain_id}/limit-order/{path}/{endpoint}'
    )


@pytest.mark.asyncio()
@patch(
    'meta_aggregation_api.providers.one_inch_v5.OneInchProviderV5.get_response',
    new_callable=AsyncMock,
)
async def test_get_orders_by_trader(get_response_mock: AsyncMock, one_inch_provider):
    get_response_mock.return_value = []
    trader = 'test_trader'
    maker_token = 'test_maker_token'
    taker_token = 'test_taker_token'
    chain_id = 1
    path = 'address'
    query = {
        'limit': 100,
        'page': 1,
        'sortBy': 'createDateTime',
        'makerAsset': maker_token,
        'takerAsset': taker_token,
    }
    url = one_inch_provider._limit_order_path_builder(
        LIMIT_ORDER_VERSION, path, trader, chain_id
    )
    await one_inch_provider.get_orders_by_trader(
        chain_id=chain_id,
        trader=trader,
        maker_token=maker_token,
        taker_token=taker_token,
    )
    get_response_mock.assert_awaited_with(url, query)


@pytest.mark.asyncio()
@patch(
    'meta_aggregation_api.providers.one_inch_v5.OneInchProviderV5.get_response',
    new_callable=AsyncMock,
)
async def test_get_order_by_hash(get_response_mock: AsyncMock, one_inch_provider):
    get_response_mock.return_value = []
    order_hash = 'test_order_hash'
    chain_id = 1
    path = 'events'
    query = None
    url = one_inch_provider._limit_order_path_builder(
        LIMIT_ORDER_VERSION, path, order_hash, chain_id
    )
    await one_inch_provider.get_order_by_hash(
        chain_id=chain_id,
        order_hash=order_hash,
    )
    get_response_mock.assert_awaited_with(url, query)


@pytest.mark.asyncio()
async def test_get_swap_quote_raises(one_inch_provider):
    with pytest.raises(ValueError, match='chain_id is required'):
        await one_inch_provider.get_swap_quote(
            buy_token='test_maker_token',
            sell_token='test_taker_token',
            sell_amount='test_maker_amount',
            slippage_percentage=1,
            taker_address='test_taker_address',
        )
    with pytest.raises(ValueError, match='Taker address is required'):
        await one_inch_provider.get_swap_quote(
            chain_id=1,
            buy_token='test_maker_token',
            sell_token='test_taker_token',
            sell_amount='test_maker_amount',
            slippage_percentage=1,
            taker_address=None,
        )


@pytest.mark.asyncio()
@patch(
    'meta_aggregation_api.providers.one_inch_v5.OneInchProviderV5.get_response',
    new_callable=AsyncMock,
)
async def test_get_swap_quote(get_response_mock: AsyncMock, one_inch_provider):
    get_response_mock.return_value = {
        'toTokenAmount': 1,
        'fromTokenAmount': 2,
        'fromToken': {
            'decimals': 18,
        },
        'toToken': {
            'decimals': 18,
        },
        'protocols': [],
        'tx': {
            'gas': 3,
            'to': 'test_to',
            'value': 4,
            'gasPrice': 5,
            'data': 'test_data',
        },
    }
    chain_id = 56
    buy_token = 'test_maker_token'
    sell_token = 'test_taker_token'
    sell_amount = 1234
    slippage_percentage = 1
    taker_address = 'test_taker_address'
    path = 'swap'
    query = {
        'toTokenAddress': buy_token,
        'fromTokenAddress': sell_token,
        'amount': sell_amount,
        'slippage': slippage_percentage * 100,
        'fromAddress': taker_address,
        'disableEstimate': 'true',
        'complexityLevel': 2,
        'mainRouteParts': 10,
        'parts': 50,
        'virtualParts': 50,
    }
    url = one_inch_provider._trading_api_path_builder(path, chain_id)
    res = await one_inch_provider.get_swap_quote(
        chain_id=chain_id,
        buy_token=buy_token,
        sell_token=sell_token,
        sell_amount=sell_amount,
        slippage_percentage=slippage_percentage,
        taker_address=taker_address,
        ignore_checks=True,
    )
    get_response_mock.assert_awaited_with(url, query)
    assert res
    assert isinstance(res, ProviderQuoteResponse)


def test_handle_exception_key_error(one_inch_provider, caplog):
    exc = one_inch_provider.handle_exception(KeyError('test'))
    assert caplog.text
    assert isinstance(exc, ParseResponseError)


def test_handle_exception_client_response_error(one_inch_provider, caplog):
    exc = one_inch_provider.handle_exception(
        ClientResponseError(
            RequestInfo(url='abc', method='GET', headers=None),
            None,
            message='not enough allowance',
        )
    )
    assert caplog.text
    assert isinstance(exc, AllowanceError)
