from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock

import pytest
from web3 import Web3

from meta_aggregation_api.config import config, providers
from meta_aggregation_api.models.meta_agg_models import ProviderPriceResponse
from meta_aggregation_api.services.meta_aggregation_service import (get_token_allowance,
                                                                    get_approve_cost,
                                                                    get_approve_costs_per_provider,
                                                                    get_swap_meta_price,
                                                                    get_decimals_for_native_and_buy_token,
                                                                    choose_best_provider,
                                                                    get_meta_swap_quote)
from meta_aggregation_api.utils.errors import ProviderNotFound


@pytest.mark.asyncio()
async def test_get_token_allowance():
    contract_mock = Mock()
    allowance_mock: Mock = contract_mock.functions.allowance
    allowance_mock.return_value.call = AsyncMock()
    call_mock = allowance_mock.return_value.call

    token_address = '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'
    owner_address = '0x61e1A8041186CeB8a561F6F264e8B2BB2E20e06D'
    spender_address = '0xdef1c0ded9bec7f1a1670819833240f027b25eff'

    await get_token_allowance(
        token_address=token_address,
        owner_address=owner_address,
        spender_address=spender_address,
        erc20_contract=contract_mock,
    )
    allowance_mock.assert_called_with(
        Web3.toChecksumAddress(owner_address),
        Web3.toChecksumAddress(spender_address),
    )
    call_mock.assert_awaited_once_with({'to': Web3.toChecksumAddress(token_address)})


@pytest.mark.asyncio()
async def test_get_token_allowance_for_native_token():
    contract_mock = Mock()
    allowance_mock: Mock = contract_mock.functions.allowance
    allowance_mock.return_value.call = AsyncMock()

    token_address = config.NATIVE_TOKEN_ADDRESS
    owner_address = '0x61e1A8041186CeB8a561F6F264e8B2BB2E20e06D'
    spender_address = '0xdef1c0ded9bec7f1a1670819833240f027b25eff'

    allowance = await get_token_allowance(
        token_address=token_address,
        owner_address=owner_address,
        spender_address=spender_address,
        erc20_contract=contract_mock,
    )
    allowance_mock.assert_not_called()
    assert allowance == 2 ** 256 - 1


@pytest.mark.asyncio()
async def test_get_approve_cost():
    owner_address = '0x61e1A8041186CeB8a561F6F264e8B2BB2E20e06D'
    spender_address = '0xdef1c0ded9bec7f1a1670819833240f027b25eff'

    contract_mock = Mock()
    approve_mock = contract_mock.functions.approve
    approve_mock.return_value.estimate_gas = AsyncMock()
    estimate_gas_mock = approve_mock.return_value.estimate_gas

    await get_approve_cost(owner_address, spender_address, contract_mock)
    approve_mock.assert_called_once_with(
        Web3.toChecksumAddress(spender_address),
        2 ** 256 - 1,
    )
    estimate_gas_mock.assert_called_once_with(
        {'from': Web3.toChecksumAddress(owner_address)},
    )


@pytest.mark.asyncio()
@pytest.mark.parametrize('sell_amount, approve_called', ((10000, True), (1, False)))
async def test_get_approve_costs_per_provider(sell_amount: int, approve_called: bool):
    chain_id = 1
    sell_token = '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'
    taker_address = '0x61e1A8041186CeB8a561F6F264e8B2BB2E20e06D'
    erc20_contract = Mock()
    allowance_patcher = patch(
        'meta_aggregation_api.services.meta_aggregation_service.get_token_allowance')
    approve_patcher = patch(
        'meta_aggregation_api.services.meta_aggregation_service.get_approve_cost')
    allowance_mock = allowance_patcher.start()
    approve_mock = approve_patcher.start()
    allowance_mock.return_value = 10
    providers_ = providers.get_providers_on_chain(chain_id)['market_order']
    await get_approve_costs_per_provider(sell_token, erc20_contract, sell_amount,
                                         providers_, taker_address)
    allowance_mock.assert_called()
    if approve_called:
        assert approve_mock.call_count == len(providers_)
    else:
        approve_mock.assert_not_called()


@pytest.mark.asyncio()
async def test_get_approve_cost_per_provider_no_taker():
    sell_token = '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'
    erc20_contract = Mock()
    taker_address = None
    sell_amount = 10000
    providers_ = providers.get_providers_on_chain(1)['market_order']
    approves = await get_approve_costs_per_provider(sell_token, erc20_contract,
                                                    sell_amount, providers_,
                                                    taker_address)
    assert erc20_contract.functions.approve.call_count == 0
    for approve in approves.values():
        assert approve == 0


@pytest.mark.asyncio()
@patch('meta_aggregation_api.providers.zerox_v1.ZeroXProviderV1.get_swap_price',
       new_callable=AsyncMock)
@patch('meta_aggregation_api.providers.one_inch_v5.OneInchProviderV5.get_swap_price',
       new_callable=AsyncMock)
async def test_get_swap_meta_price_no_price(
    one_inch_mock: AsyncMock,
    zerox_mock: AsyncMock,
    aiohttp_session,
):
    """Test that get_swap_meta_quote raise exc if no quote is found."""
    zerox_mock.return_value = None
    one_inch_mock.return_value = None
    approve_patcher = patch(
        'meta_aggregation_api.services.meta_aggregation_service.get_approve_costs_per_provider')
    approve_patcher.start()
    test_str = '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'
    test_str_2 = '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'
    test_int = 10
    with pytest.raises(ValueError, match='No prices found'):
        await get_swap_meta_price(
            test_str, test_str_2, test_int, test_int, test_int, test_int, test_str,
            test_str, None)


@pytest.mark.asyncio()
@patch(
    'meta_aggregation_api.services.meta_aggregation_service.DexGuru.get_token_inventory_by_address',
    new_callable=AsyncMock)
@pytest.mark.parametrize(
    'token_address, call_count',
    (
        ('test_token', 1),
        (config.NATIVE_TOKEN_ADDRESS, 0),
        ('0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2', 0)
    )
)
async def test_get_decimals_for_native_and_buy_token_call_count(
    get_token_mock: AsyncMock,
    token_address: str,
    call_count: int,
):
    await get_decimals_for_native_and_buy_token(1, token_address)
    assert get_token_mock.call_count == call_count


@pytest.mark.parametrize(
    'buy_amount_1__gas_1__gas_price_1__approve_cost_1,buy_amount_2__gas_2__gas_price_2__approve_cost_2,expected_provider',
    (
        (('1', '1', '1', '0'), ('2', '3', '1', '0'), 'provider_2'),
        (('10', '1', '1', '15'), ('10', '1', '1', '10'), 'provider_2'),
        (('10', '2', '1', '0'), ('9', '1', '1', '0'), 'provider_1'),
        ((15, 1, 1, 0), (30, 1, 1, 10), 'provider_2'),
        ((20, 4, 2, 0), (10, 1, 1, 0), 'provider_1'),
        ((20, 600, 2, 0), (10, 1, 1, 0), 'provider_1'),
    )
)
def test_choose_best_provider(
    buy_amount_1__gas_1__gas_price_1__approve_cost_1,
    buy_amount_2__gas_2__gas_price_2__approve_cost_2,
    expected_provider,
):
    token_price_native = 1000
    provider_1 = 'provider_1'
    provider_2 = 'provider_2'
    buy_amount_1, gas_1, gas_price_1, approve_cost_1 = buy_amount_1__gas_1__gas_price_1__approve_cost_1
    buy_amount_2, gas_2, gas_price_2, approve_cost_2 = buy_amount_2__gas_2__gas_price_2__approve_cost_2
    quote_1 = ProviderPriceResponse(
        provider=provider_1,
        sources=[],
        buy_amount=Decimal(str(buy_amount_1)) * 2,
        gas=gas_1,
        gas_price=gas_price_1,
        value=1,
        price=1,
        sell_amount=1,
    )
    quote_2 = ProviderPriceResponse(
        provider=provider_2,
        sources=[],
        buy_amount=Decimal(str(buy_amount_2)) * 2,
        gas=gas_2,
        gas_price=gas_price_2,
        value=1,
        price=1,
        sell_amount=1,
    )
    approve_costs = {provider_1: approve_cost_1, provider_2: approve_cost_2}
    quotes = {provider_1: quote_1, provider_2: quote_2}
    res = choose_best_provider(quotes, approve_costs, native_decimals=1,
                               buy_token_decimals=1, buy_token_price=token_price_native)
    assert res == (expected_provider, quotes[expected_provider])


@pytest.mark.asyncio()
async def test_get_meta_swap_quote():
    provider = 'invalid_provider'
    with pytest.raises(ProviderNotFound):
        await get_meta_swap_quote(
            provider=provider,
            sell_token='test',
            buy_token='test',
            sell_amount=1,
            chain_id=1,
            taker_address='test',
        )
