from statistics import mean
from time import time
from typing import Optional
from urllib.parse import urljoin

from web3 import Web3

from clients.blockchain.custom_http_provider import CustomHTTPProvider
from config import config, chains
from utils.async_utils import async_from_sync
from utils.logger import get_logger

logger = get_logger(__name__)


async def get_gas_prices(chain_id: int) -> dict:
    logger.debug('Getting gas prices for network %s', chain_id)
    web3_url = urljoin(config.WEB3_URL, f'/{chain_id}/{config.PUBLIC_KEY}')
    w3 = Web3(CustomHTTPProvider(endpoint_uri=web3_url))
    if chains.get_chain_by_id(chain_id).eip1559:
        return await get_gas_prices_eip1559(w3)
    return await get_gas_prices_legacy(w3)


@async_from_sync
def get_gas_prices_eip1559(w3: Web3) -> Optional[dict]:
    try:
        gas_history = w3.eth.fee_history(4, 'latest', [60, 75, 90])
    except (ValueError) as e:
        return None
    reward = gas_history['reward']
    # baseFee for next block
    base_fee = gas_history['baseFeePerGas'][-1]

    reward_fast = [_[0] for _ in reward]
    reward_instant = [_[1] for _ in reward]
    reward_overkill = [_[2] for _ in reward]

    fast_priority = int(mean(reward_fast))
    instant_priority = int(mean(reward_instant))
    overkill_priority = int(mean(reward_overkill))
    return {
        'source': 'DEXGURU',
        'timestamp': int(time()),
        'eip-1559': {
            'fast': {
                'maxFee': base_fee + fast_priority,
                'baseFee': base_fee,
                'maxPriorityFee': fast_priority,
            },
            'instant': {
                'maxFee': base_fee + instant_priority,
                'baseFee': base_fee,
                'maxPriorityFee': instant_priority,
            },
            'overkill': {
                'maxFee': base_fee + overkill_priority,
                'baseFee': base_fee,
                'maxPriorityFee': overkill_priority,
            }
        }
    }


@async_from_sync
def get_gas_prices_legacy(w3: Web3) -> dict:
    gas_price = w3.eth.gas_price
    return {
        'source': 'DEXGURU',
        'timestamp': int(time()),
        'fast': gas_price,
        'instant': gas_price,
        'overkill': gas_price
    }
