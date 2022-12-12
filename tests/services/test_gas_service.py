from unittest.mock import patch, AsyncMock, Mock

import pytest
from web3.datastructures import AttributeDict

from services.gas_service import get_gas_prices, get_gas_prices_legacy, get_gas_prices_eip1559


@pytest.mark.asyncio()
@patch('clients.blockchain.web3_client.Web3Client', new_callable=Mock)
@patch('services.gas_service.get_gas_prices_eip1559', new_callable=AsyncMock)
@patch('services.gas_service.get_gas_prices_legacy', new_callable=AsyncMock)
async def test_get_gas_priceeip_chain(get_legacy_gas_mock: AsyncMock, get_eip_gas_mock: AsyncMock, web3_mock: Mock):
    await get_gas_prices(1)
    get_eip_gas_mock.assert_awaited_once()
    get_legacy_gas_mock.assert_not_awaited()


@pytest.mark.asyncio()
@patch('services.gas_service.Web3Client', new_callable=Mock)
@patch('services.gas_service.get_gas_prices_eip1559', new_callable=AsyncMock)
@patch('services.gas_service.get_gas_prices_legacy', new_callable=AsyncMock)
async def test_get_gas_price_legacy_chain(get_legacy_gas_mock: AsyncMock, get_eip_gas_mock: AsyncMock, web3_mock: Mock):
    await get_gas_prices(56)
    get_eip_gas_mock.assert_not_awaited()
    get_legacy_gas_mock.assert_awaited_once()


@pytest.mark.asyncio()
@patch('services.gas_service.Web3Client', new_callable=Mock)
async def test_get_gas_price_legacy(web3_mock: AsyncMock):
    web3_mock.w3.eth.gas_price = AsyncMock(return_value=123)
    await get_gas_prices_legacy(web3_mock)
    web3_mock.w3.eth.gas_price.assert_called_once()


@pytest.mark.asyncio()
@patch('services.gas_service.Web3Client', new_callable=Mock)
async def test_get_gas_price_eip1559(web3_mock: AsyncMock):
    web3_mock.w3.eth.fee_history.return_value = AttributeDict(
        {
            'oldestBlock': 13304966,
            'reward': [
                [1500000000, 1500000000, 3202574264],
                [1500000000, 2000000000, 6931501329],
                [1500000000, 1500000000, 1500000000],
                [1500000000, 1500000000, 2000000000]
            ],
            'baseFeePerGas': [56427293104, 53420243156, 59910824543, 59720412466, 61376457015],
            'gasUsedRatio': [0.2868372, 0.9860016027682301, 0.48728696666666665, 0.6109198333333333]
        }
    )
    await get_gas_prices_eip1559(web3_mock)
    web3_mock.w3.eth.fee_history.assert_awaited_once()
