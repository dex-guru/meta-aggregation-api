from statistics import mean
from time import time
from typing import Optional

from aiocache import cached
from requests import ReadTimeout
from tenacity import retry, retry_if_exception_type

from clients.blockchain.web3_client import Web3Client
from config import chains
from models.gas_models import GasResponse
from utils.common import get_web3_url
from utils.logger import get_logger

GAS_SOURCE = 'DEXGURU'

logger = get_logger(__name__)


@cached(ttl=5)
async def get_gas_prices(chain_id: int) -> GasResponse:
    logger.debug('Getting gas prices for network %s', chain_id)
    web3_client = Web3Client(get_web3_url(chain_id))
    if chains.get_chain_by_id(chain_id).eip1559:
        return await get_gas_prices_eip1559(web3_client)
    return await get_gas_prices_legacy(web3_client)


@cached(ttl=5)
@retry(retry=retry_if_exception_type(ReadTimeout), stop=3)
async def get_base_gas_price(chain_id: int) -> int:
    logger.debug('Getting base gas price for network %s', chain_id)
    web3_client = Web3Client(get_web3_url(chain_id))
    return await web3_client.w3.eth.gas_price


@retry(retry=retry_if_exception_type(ReadTimeout), stop=3)
async def get_gas_prices_eip1559(w3: Web3Client) -> Optional[GasResponse]:
    gas_history = await w3.w3.eth.fee_history(4, 'latest', [60, 75, 90])
    reward = gas_history['reward']
    # baseFee for next block
    base_fee = gas_history['baseFeePerGas'][-1]

    reward_fast = [_[0] for _ in reward]
    reward_instant = [_[1] for _ in reward]
    reward_overkill = [_[2] for _ in reward]

    fast_priority = int(mean(reward_fast))
    instant_priority = int(mean(reward_instant))
    overkill_priority = int(mean(reward_overkill))
    return GasResponse.parse_obj({
        'source': GAS_SOURCE,
        'timestamp': int(time()),
        'eip1559': {
            'fast': {
                'max_fee': base_fee + fast_priority,
                'base_fee': base_fee,
                'max_priority_fee': fast_priority,
            },
            'instant': {
                'max_fee': base_fee + instant_priority,
                'base_fee': base_fee,
                'max_priority_fee': instant_priority,
            },
            'overkill': {
                'max_fee': base_fee + overkill_priority,
                'base_fee': base_fee,
                'max_priority_fee': overkill_priority,
            }
        }
    })


@retry(retry=retry_if_exception_type(ReadTimeout), stop=3)
async def get_gas_prices_legacy(w3: Web3Client) -> GasResponse:
    gas_price = await w3.w3.eth.gas_price
    return GasResponse.parse_obj({
        'source': GAS_SOURCE,
        'timestamp': int(time()),
        'legacy': {
            'fast': gas_price,
            'instant': gas_price,
            'overkill': gas_price,
        }
    })
