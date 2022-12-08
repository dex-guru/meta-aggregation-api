from pathlib import Path
from typing import Optional, Type, Union, List

import ujson
from web3 import Web3
from web3.contract import Contract
from web3.eth import AsyncEth
from web3.middleware import geth_poa_middleware, async_geth_poa_middleware
from web3.net import AsyncNet
from web3.types import FeeHistory

from clients.blockchain.custom_http_provider import AsyncCustomHTTPProvider
from utils.logger import get_logger

ERC20_ABI_PATH = Path(__file__).parent / 'abi' / 'ERC20.json'

logger = get_logger(__name__)


class Web3Client:

    def __init__(self, uri: str):
        self.w3 = Web3(
            AsyncCustomHTTPProvider(endpoint_uri=uri),
            modules={
                "eth": (AsyncEth,),
                "net": (AsyncNet,),
            },
            middlewares=[]
        )
        self.w3.middleware_onion.inject(async_geth_poa_middleware, layer=0)

        with open(ERC20_ABI_PATH) as fh:
            self.erc20_abi = ujson.load(fh)

    async def get_erc20_contract(self, address: Optional[str] = None) -> Union[Type[Contract], Contract]:
        params = {'abi': self.erc20_abi}
        if address:
            params['address'] = Web3.toChecksumAddress(address)
        return await self.w3.eth.contract(**params)

    async def get_fee_history(self,
                              block_count: int,
                              newest_block: Union[int, str] = 'latest',
                              reward_percentiles: Optional[List[float]] = None) -> Optional[FeeHistory]:
        node_uri = self.w3.manager.provider.endpoint_uri
        try:
            response: FeeHistory = await self.w3.eth.fee_history(block_count, newest_block, reward_percentiles)
        except ValueError as e:
            logger.error(f"Issue getting fee prices, probably block is not in cache of {node_uri} anymore {e}")
            return None
        if 'reward' not in response:
            logger.error(f'Node {node_uri} not have fee history data for block {newest_block}')
            return None
        return response
