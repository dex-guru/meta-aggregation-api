from unittest.mock import AsyncMock, Mock, patch

import pytest

from meta_aggregation_api.services.gas_service import get_gas_prices


@pytest.mark.asyncio()
@patch(
    'meta_aggregation_api.clients.blockchain.web3_client.Web3Client', new_callable=Mock
)
@patch(
    'meta_aggregation_api.services.gas_service.get_gas_prices_eip1559',
    new_callable=AsyncMock,
)
@patch(
    'meta_aggregation_api.services.gas_service.get_gas_prices_legacy',
    new_callable=AsyncMock,
)
async def test_get_gas_price_eip_chain(
    get_legacy_gas_mock: AsyncMock, get_eip_gas_mock: AsyncMock, web3_mock: Mock
):
    await get_gas_prices(1)
    get_eip_gas_mock.assert_awaited_once()
    get_legacy_gas_mock.assert_not_awaited()


@pytest.mark.asyncio()
@patch('meta_aggregation_api.services.gas_service.Web3Client', new_callable=Mock)
@patch(
    'meta_aggregation_api.services.gas_service.get_gas_prices_eip1559',
    new_callable=AsyncMock,
)
@patch(
    'meta_aggregation_api.services.gas_service.get_gas_prices_legacy',
    new_callable=AsyncMock,
)
async def test_get_gas_price_legacy_chain(
    get_legacy_gas_mock: AsyncMock, get_eip_gas_mock: AsyncMock, web3_mock: Mock
):
    await get_gas_prices(56)
    get_eip_gas_mock.assert_not_awaited()
    get_legacy_gas_mock.assert_awaited_once()
