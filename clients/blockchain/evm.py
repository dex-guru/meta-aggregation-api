from pathlib import Path
from typing import Optional, Type, Union

import ujson
from web3 import Web3
from web3.contract import Contract
from web3.middleware import geth_poa_middleware

from clients.blockchain.custom_http_provider import CustomHTTPProvider

ERC20_ABI_PATH = Path(__file__).parent / 'abi' / 'ERC20.json'


class EVMBase:

    def __init__(self, uri: str):
        self.w3 = Web3(CustomHTTPProvider(endpoint_uri=uri))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        with open(ERC20_ABI_PATH) as fh:
            self.erc20_abi = ujson.load(fh)

    def get_erc20_contract(self, address: Optional[str] = None) -> Union[Type[Contract], Contract]:
        params = {'abi': self.erc20_abi}
        if address:
            params['address'] = Web3.toChecksumAddress(address)
        return self.w3.eth.contract(**params)
