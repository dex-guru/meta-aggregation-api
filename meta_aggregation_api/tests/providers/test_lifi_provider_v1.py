import pytest

from meta_aggregation_api.tests.fixtures.providers_clients import lifi_provider_v1


@pytest.mark.asyncio
async def test_get_swap_quote(lifi_provider_v1):
    # http://localhost:8000/v1/market/1/price/all?
    # buyToken=0x2260fac5e5542a773aa44fbcfedf7c193bc2c599&
    # sellAmount=253785440705476742&
    # sellToken=0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE&
    # feeRecipient=0x720c9244473Dfc596547c1f7B6261c7112A3dad4&chainId=1&
    # takerAddress=0xA0942D8352FFaBCc0f6dEE32b2b081C703e726A5
    params = {
        'buy_token': '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c',
        'sell_amount': '253785440705476742',
        'sell_token': '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE',
        'fee_recipient': "0x720c9244473Dfc596547c1f7B6261c7112A3dad4",
        'chain_id': 1,
        'taker_address': '0xA0942D8352FFaBCc0f6dEE32b2b081C703e726A5',
        'to_chain_id': 56
    }

    swap_quote = await lifi_provider_v1.get_swap_quote(**params)
    assert swap_quote


@pytest.mark.asyncio
async def test_get_swap_price(lifi_provider_v1):
    # http://localhost:8000/v1/market/1/price/all?
    # buyToken=0x2260fac5e5542a773aa44fbcfedf7c193bc2c599&
    # sellAmount=253785440705476742&
    # sellToken=0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE&
    # feeRecipient=0x720c9244473Dfc596547c1f7B6261c7112A3dad4&chainId=1&
    # takerAddress=0xA0942D8352FFaBCc0f6dEE32b2b081C703e726A5
    params = {
        'buy_token': '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c',
        'sell_amount': '253785440705476742',
        'sell_token': '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE',
        'fee_recipient': "0x720c9244473Dfc596547c1f7B6261c7112A3dad4",
        'chain_id': 1,
        'taker_address': '0xA0942D8352FFaBCc0f6dEE32b2b081C703e726A5',
        'to_chain_id': 56
    }

    get_swap_price = await lifi_provider_v1.get_swap_price(**params)
    assert get_swap_price
