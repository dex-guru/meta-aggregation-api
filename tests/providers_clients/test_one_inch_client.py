from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import ClientResponseError, RequestInfo

from models.meta_agg_models import SwapQuoteResponse
from provider_clients.one_inch_provider import LIMIT_ORDER_VERSION, TRADING_API_VERSION
from models.chain import TokenModel
from utils.errors import ParseResponseError, AllowanceError


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
    assert url == f'https://{one_inch_provider.LIMIT_ORDERS_DOMAIN}/v{version}/{chain_id}/limit-order/{path}/{endpoint}'


@pytest.mark.asyncio()
@patch('provider_clients.one_inch_provider.OneInchProvider.get_response', new_callable=AsyncMock)
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
    url = one_inch_provider._limit_order_path_builder(LIMIT_ORDER_VERSION, path, trader, chain_id)
    await one_inch_provider.get_orders_by_trader(
        chain_id=chain_id,
        trader=trader,
        maker_token=maker_token,
        taker_token=taker_token,
    )
    get_response_mock.assert_awaited_with(url, query)


@pytest.mark.asyncio()
@patch('clients.proxy.api_providers.one_inch_provider.OneInchProvider.get_response', new_callable=AsyncMock)
async def test_get_order_by_hash(get_response_mock: AsyncMock, one_inch_provider):
    get_response_mock.return_value = []
    network = 'eth'
    order_hash = 'test_order_hash'
    chain_id = 1
    path = 'events'
    query = None
    url = one_inch_provider._limit_order_path_builder(LIMIT_ORDER_VERSION, path, order_hash, chain_id)
    await one_inch_provider.get_order_by_hash(
        network=network,
        order_hash=order_hash,
    )
    get_response_mock.assert_awaited_with(url, query)


@pytest.mark.asyncio()
async def test_get_swap_quote_raises(one_inch_provider):
    with pytest.raises(ValueError):
        await one_inch_provider.get_swap_quote(
            network=None,
            buy_token='test_maker_token',
            sell_token='test_taker_token',
            sell_amount='test_maker_amount',
            slippage_percentage=1,
            taker_address='test_taker_address',
        )
    with pytest.raises(ValueError):
        await one_inch_provider.get_swap_quote(
            network='test_network',
            buy_token='test_maker_token',
            sell_token='test_taker_token',
            sell_amount='test_maker_amount',
            slippage_percentage=1,
            taker_address=None,
        )


@pytest.mark.asyncio()
@patch('clients.proxy.api_providers.one_inch_provider.OneInchProvider.calculate_price_from_amounts', new_callable=AsyncMock)
@patch('clients.proxy.api_providers.one_inch_provider.OneInchProvider.get_response', new_callable=AsyncMock)
async def test_get_swap_quote(get_response_mock: AsyncMock, calc_price_mock: AsyncMock, one_inch_provider):
    get_response_mock.return_value = {
        'toTokenAmount': 1,
        'fromTokenAmount': 2,
        'protocols': [],
        'tx': {
            'gas': 3,
            'to': 'test_to',
            'value': 4,
            'gasPrice': 5,
            'data': 'test_data',
        },
    }
    calc_price_mock.return_value = 123
    network = 'bsc'
    chain_id = 56
    buy_token = 'test_maker_token'
    sell_token = 'test_taker_token'
    sell_amount = 'test_maker_amount'
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
    url = one_inch_provider._trading_api_path_builder(TRADING_API_VERSION, path, chain_id)
    res = await one_inch_provider.get_swap_quote(
        network=network,
        buy_token=buy_token,
        sell_token=sell_token,
        sell_amount=sell_amount,
        slippage_percentage=slippage_percentage,
        taker_address=taker_address,
        ignore_checks=True,
    )
    get_response_mock.assert_awaited_with(url, query)
    assert res
    assert isinstance(res, SwapQuoteResponse)


@pytest.mark.asyncio()
@patch('services.erc20_tokens_service.ERC20TokensService.get_erc20_token_by_address_network', new_callable=AsyncMock)
async def test_calculate_price_from_amounts(get_erc20_mock: AsyncMock, one_inch_provider):
    network = 'arbitrum'
    buy_token = '0x0000000000000000000000000000000000000000'
    sell_token = '0x0000000000000000000000000000000000000001'
    buy_amount = 1
    sell_amount = 2
    get_erc20_mock.side_effect = [TokenModel(
        address=buy_token,
        name='test_maker_token',
        symbol='test_maker_token',
        decimals=18,
    ), TokenModel(
        address=sell_token,
        name='test_taker_token',
        symbol='test_taker_token',
        decimals=18,
    )]
    res = await one_inch_provider.calculate_price_from_amounts(
        network, buy_token, sell_token, buy_amount, sell_amount
    )
    assert res == 0.5


def test_handle_exception_key_error(one_inch_provider, caplog):
    exc = one_inch_provider.handle_exception(KeyError('test'))
    assert caplog.text
    assert caplog.handler.records[0].module == 'base_provider'
    assert isinstance(exc, ParseResponseError)


def test_handle_exception_client_response_error(one_inch_provider, caplog):
    exc = one_inch_provider.handle_exception(ClientResponseError(
        RequestInfo(url='abc', method='GET', headers=None), None, message='not enough allowance'))
    assert caplog.text
    assert isinstance(exc, AllowanceError)
