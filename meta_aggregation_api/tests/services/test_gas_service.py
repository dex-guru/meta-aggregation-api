from unittest import mock
from unittest.mock import Mock, patch

import pytest

from meta_aggregation_api.services.gas_service import GasService


@pytest.mark.asyncio()
async def test_get_gas_price_eip_chain(
    config,
    gas_service: GasService,
):
    with (
        mock.patch.object(gas_service, 'get_gas_prices_eip1559') as get_eip_gas_mock,
        mock.patch.object(gas_service, 'get_gas_prices_legacy') as get_legacy_gas_mock,
        mock.patch('meta_aggregation_api.clients.blockchain.web3_client.Web3Client'),
    ):
        await gas_service.get_gas_prices(1)
        get_eip_gas_mock.assert_awaited_once()
        get_legacy_gas_mock.assert_not_awaited()


@pytest.mark.asyncio()
@patch('meta_aggregation_api.services.gas_service.Web3Client')
async def test_get_gas_price_legacy_chain(
    web3_mock: Mock,
    gas_service: GasService,
):
    assert not gas_service.get_gas_prices.cache._cache
    with (
        mock.patch.object(gas_service, 'get_gas_prices_eip1559') as get_eip_gas_mock,
        mock.patch.object(gas_service, 'get_gas_prices_legacy') as get_legacy_gas_mock,
    ):
        await gas_service.get_gas_prices(56)
        get_eip_gas_mock.assert_not_awaited()
        get_legacy_gas_mock.assert_awaited_once()
