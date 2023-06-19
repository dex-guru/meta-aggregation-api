import asyncio
from decimal import Decimal
from functools import partial
from typing import List, Optional, Tuple

import aiohttp
from aiocache import cached
from dexguru_sdk import DexGuru
from web3 import Web3
from web3.contract import AsyncContract

from meta_aggregation_api.clients.apm_client import ApmClient
from meta_aggregation_api.clients.blockchain.web3_client import Web3Client
from meta_aggregation_api.config import Config
from meta_aggregation_api.config.providers import ProvidersConfig
from meta_aggregation_api.models.meta_agg_models import (
    MetaPriceModel,
    ProviderPriceResponse,
    ProviderQuoteResponse,
)
from meta_aggregation_api.providers import ProviderRegistry, CrossChainProvider
from meta_aggregation_api.services.chains import ChainsConfig
from meta_aggregation_api.services.gas_service import GasService
from meta_aggregation_api.utils.cache import get_cache_config
from meta_aggregation_api.utils.common import get_web3_url
from meta_aggregation_api.utils.errors import ProviderNotFound
from meta_aggregation_api.utils.logger import get_logger

logger = get_logger(__name__)


class MetaAggregationService:
    def __init__(
        self,
        *,
        config: Config,
        gas_service: GasService,
        chains: ChainsConfig,
        providers: ProvidersConfig,
        session: aiohttp.ClientSession,
        apm_client: ApmClient,
        provider_registry: ProviderRegistry,
        crosschain_provider_registry: ProviderRegistry,
    ):
        self.provider_registry = provider_registry
        self.crosschain_provider_registry = crosschain_provider_registry
        self.config = config
        self.providers = providers
        self.gas_service = gas_service
        self.chains = chains
        self.session = session
        self.apm_client = apm_client

        cached_ = partial(cached, **get_cache_config(config))

        self.get_token_allowance = cached_(ttl=5, noself=True)(self.get_token_allowance)
        self.get_approve_cost = cached_(ttl=5, noself=False)(self.get_approve_cost)
        self.get_decimals_for_native_and_buy_token = cached_(60 * 60 * 2, noself=True)(
            self.get_decimals_for_native_and_buy_token
        )
        self.get_swap_meta_price = cached_(ttl=5, noself=True)(self.get_swap_meta_price)

    async def get_token_allowance(
        self,
        token_address: str,
        spender_address: str,
        erc20_contract: AsyncContract,
        owner_address: Optional[str] = None,
    ) -> int:
        logger.debug('Getting allowance for token %s', token_address)
        if token_address == self.config.NATIVE_TOKEN_ADDRESS or not owner_address:
            return 2**256 - 1
        owner_address = Web3.toChecksumAddress(owner_address)
        spender_address = Web3.toChecksumAddress(spender_address)
        token_address = Web3.toChecksumAddress(token_address)
        allowance = await erc20_contract.functions.allowance(
            owner_address, spender_address
        ).call({'to': token_address})
        return allowance

    @staticmethod
    async def get_approve_cost(
        owner_address: str,
        spender_address: str,
        erc20_contract: AsyncContract,
    ) -> int:
        logger.debug('Getting approve cost for owner %s', owner_address)
        owner_address = Web3.toChecksumAddress(owner_address)
        spender_address = Web3.toChecksumAddress(spender_address)
        approve_cost = await erc20_contract.functions.approve(
            spender_address, 2**256 - 1
        ).estimate_gas({'from': owner_address})
        return approve_cost

    async def get_approve_costs_per_provider(
        self,
        sell_token: str,
        erc20_contract: AsyncContract,
        sell_amount: int,
        providers_: list[dict],
        taker_address: Optional[str] = None,
    ) -> dict[str, int]:
        """
        To make swap, user should approve spending of sell token by spender contract.
        This function checks allowance for each provider on sell_token, compares it with sell_amount
        and returns approve costs. If allowance is enough, approve cost will be 0.

        Args:
            sell_token:str: Specify the token address that is sold in the swap
            erc20_contract: AsyncContract: Specify the erc20 contract of sell_token
            sell_amount:int: Specify the amount of tokens to sell in base units (e.g. 1 ETH = 10 ** 18)
            providers_:list[dict]: Specify the list of providers
            taker_address:Optional[str]=None: Specify the address of the user who will be using this swap.
                To make it possible to check only price, taker_address could be None and in this case approve cost will be 0.

        Returns:
            dict: Returns a dictionary with provider names as keys and approve costs as values
        """
        approve_costs_per_provider = {}
        for provider in providers_:
            if not taker_address:
                approve_costs_per_provider[provider['name']] = 0
                continue
            spender_address = provider['address']
            allowance = await self.get_token_allowance(
                sell_token, spender_address, erc20_contract, taker_address
            )
            logger.debug('Got allowance for token %s: %s', sell_token, allowance)
            if allowance < sell_amount:
                logger.debug('Allowance is not enough, getting approve cost')
                approve_cost = await self.get_approve_cost(
                    taker_address, spender_address, erc20_contract
                )
                approve_costs_per_provider[provider['name']] = approve_cost
            else:
                approve_costs_per_provider[provider['name']] = 0
        return approve_costs_per_provider

    async def get_swap_meta_price(
        self,
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        chain_id: int,
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = None,
        taker_address: Optional[str] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None,
    ) -> List[MetaPriceModel]:
        """
        Get swap prices from all providers and find the best one.
        Calculating the best price based on the received tokens after swap, spent gas and approve cost.

        Args:
            buy_token:str: Specify the token address that you want to buy
            sell_token:str: Specify the token address that is sold in the swap
            sell_amount:int: Specify the amount of tokens to sell in base units (e.g. 1 ETH = 10 ** 18)
            taker_address:str: Specify the address of the user who will be using this price_response
            chain_id:int: Specify the chain on which to perform the swap
            gas_price:Optional[int]=None: Set the gas price for the transaction. If not set, the gas price will be fetched web3
            slippage_percentage:Optional[float]=None: Set a maximum percentage of slippage for the trade. (0.01 = 1%)
            fee_recipient:Optional[str]=None: Specify the address of a fee recipient
            buy_token_percentage_fee:Optional[float]=None: Specify a percentage of the buy_amount that will be used to pay fees


        Returns:
            A list of MetaPriceModel objects, which contain the following fields:
                provider:str: The name of the provider
                price_response:ProviderPriceResponse: The price_response from the provider
                approve_cost:int: The cost of the approve transaction
                is_allowed:bool: The user has enough allowance for the swap on this provider
                is_best:bool: The best price_response for the swap

        Raises:
            ValueError: If not found any possible swap for the given parameters on all providers
        """
        spender_addresses = self.providers.get_providers_on_chain(chain_id)[
            'market_order'
        ]
        web3_url = get_web3_url(chain_id, self.config)
        erc20_contract = Web3Client(web3_url, self.config).get_erc20_contract(
            sell_token
        )
        approve_costs = asyncio.create_task(
            self.get_approve_costs_per_provider(
                sell_token,
                erc20_contract,
                sell_amount,
                spender_addresses,
                taker_address,
            )
        )
        get_decimals_task = asyncio.create_task(
            self.get_decimals_for_native_and_buy_token(chain_id, buy_token)
        )

        if buy_token == self.config.NATIVE_TOKEN_ADDRESS:
            buy_token = self.chains.get_chain_by_id(chain_id).native_token.address
        get_buy_token_price_task = asyncio.create_task(
            DexGuru(
                self.config.PUBLIC_KEY, domain=self.config.PUBLIC_API_DOMAIN
            ).get_token_finance(chain_id, buy_token)
        )
        if not gas_price:
            gas_price = await self.gas_service.get_base_gas_price(chain_id)

        prices_tasks = []
        for provider in self.providers.values():
            if provider is None:
                continue
            provider_name = provider['name']

            provider_instance = self.provider_registry.get(provider_name)
            if not provider_instance:
                continue

            prices_tasks.append(
                asyncio.create_task(
                    provider_instance.get_swap_price(
                        buy_token,
                        sell_token,
                        sell_amount,
                        chain_id,
                        gas_price,
                        slippage_percentage,
                        taker_address,
                        fee_recipient,
                        buy_token_percentage_fee,
                    )
                )
            )
        prices_list = await asyncio.gather(*prices_tasks, return_exceptions=True)
        prices = {
            price.provider: price
            for price in prices_list
            if isinstance(price, ProviderPriceResponse)
        }  # {provider: price_response}
        if not any(prices):
            logger.error(
                'No prices found',
                extra={
                    'buy_token': buy_token,
                    'sell_token': sell_token,
                    'sell_amount': sell_amount,
                    'chain_id': chain_id,
                    'providers': list(prices.keys()),
                },
            )
            raise ValueError('No prices found')
        approve_costs = await approve_costs
        native_decimals, buy_token_decimals = await get_decimals_task
        buy_token_price = await get_buy_token_price_task
        buy_token_price = buy_token_price.price_eth
        best_provider, price = self.choose_best_provider(
            prices, approve_costs, native_decimals, buy_token_decimals, buy_token_price
        )
        logger.info(
            'Got swap prices for chain %s',
            chain_id,
            extra={
                'best_provider': best_provider,
                'buy_token': buy_token,
                'sell_token': sell_token,
                'taker_address': taker_address,
            },
        )
        return [
            MetaPriceModel(
                provider=provider_,
                is_allowed=approve_costs[provider_] == 0,
                price_response=price_,
                is_best=provider_ == best_provider,
                approve_cost=approve_costs[provider_],
            )
            for provider_, price_ in prices.items()
        ]

    async def get_decimals_for_native_and_buy_token(
        self, chain_id: int, buy_token: str
    ) -> Tuple[int, int]:
        """
        Get decimals for native token and buy token.
        Decimals for native token needed to calculate gas amount in base units.
        Decimals for buy token needed to calculate received tokens in base units.
        These decimals are used in calculations of the best provider.

        Args:
            chain_id:int: Specify the chain that is being queried
            buy_token:str: Address of the token that is being bought

        Returns:
            Tuple of decimals for the native token and the buy token
        """
        wrapped_native = self.chains.get_chain_by_id(chain_id).native_token
        native_decimals = wrapped_native.decimals
        buy_token = buy_token.lower()
        guru_sdk = DexGuru(self.config.PUBLIC_KEY, domain=self.config.PUBLIC_API_DOMAIN)
        if (
            buy_token == self.config.NATIVE_TOKEN_ADDRESS
            or buy_token == wrapped_native.address
        ):
            buy_token_decimals = native_decimals
        else:
            buy_token_inventory = await guru_sdk.get_token_inventory_by_address(
                chain_id, buy_token
            )
            buy_token_decimals = buy_token_inventory.decimals
        return native_decimals, buy_token_decimals

    @staticmethod
    def choose_best_provider(
        prices: dict,
        approve_costs: dict,
        native_decimals: int,
        buy_token_decimals: int,
        buy_token_price: float,
    ) -> Tuple[str, ProviderPriceResponse]:
        """
        The choose_best_provider function takes in a dictionary of quotes from all providers
        and then returns a tuple with the best provider as first element and the price_response from that provider as second element.

        Profit calculation:
            Let's say we have 2 providers, provider1 and provider2. We want to buy USDC with 0.00005 WBTC.

            TxGasCost [wei] = GasPrice * GasAmount                     gas needed for swap
            ApproveCost [wei] = GasPrice * GasAmountForApprove         gas needed for approve tx. 0 if already approved

                              (TxGasCost + ApproveCost)
            SumCost [ETH] = -------------------------                  sum amount of native token needed to pay for txs
                                 10 ** decimals

            Let's say:
                SumCost1 = 0.0001 ETH tx_gas + 0 ETH approve = 0.0001 ETH
                SumCost2 = 0.0001 ETH tx_gas + 0.0001 ETH approve = 0.0002 ETH

            --------------------------------------------------------------------------------------------------------------

                                    ReceivedToken1     1000000
            ReceivedTokenAmount1 = ---------------- = --------- = 1 USDC
                                    10 ** decimals     10 ** 6

                                    ReceivedToken2     1200000
            ReceivedTokenAmount2 = ---------------- = --------- = 1.2 USDC
                                    10 ** decimals     10 ** 6

            --------------------------------------------------------------------------------------------------------------
            Now we need to convert the values to the same units. We use the native price of the token we want to buy.

            ReceivedToken1Native = ReceivedToken1 * TokenPriceNative = 1 * 0.000805 = 0.000805 ETH
            ReceivedToken2Native = ReceivedToken2 * TokenPriceNative = 1.2 * 0.000805 = 0.000966 ETH

            --------------------------------------------------------------------------------------------------------------

            Profit1 = ReceivedToken1 - SumCost = 0.000805 ETH - 0.0001 ETH = 0.000705 ETH
            Profit2 = ReceivedToken2 - SumCost = 0.000966 ETH - 0.0002 ETH = 0.000766 ETH

            Profit2 > Profit1 => Provider2 is better, even though you have to perform an additional approval tx.

        Args:
            prices:dict[MetaSwapPriceResponse]: Prices from all providers
            approve_costs:dict: Total cost of approving tokens for each provider
            native_decimals:int: Decimals of the native token on chain
            buy_token_decimals:int: Decimals of the buy token
            buy_token_price:float: Last price of the buy token in native token

        Returns:
            Tuple with the best provider name and price object for that provider
        """
        best_provider = None
        best_price = None
        best_profit = None
        buy_token_price = Decimal(str(buy_token_price))
        for provider, price_response in prices.items():
            if not price_response:
                continue
            tx_gas_cost = Decimal(price_response.gas) * Decimal(
                price_response.gas_price
            )
            approve_gas_cost = Decimal(approve_costs[provider]) * Decimal(
                price_response.gas_price
            )
            sum_cost = (tx_gas_cost + approve_gas_cost) / Decimal(10**native_decimals)
            buy_token_amount = Decimal(price_response.buy_amount) / Decimal(
                10**buy_token_decimals
            )
            buy_token_in_native = buy_token_amount * buy_token_price
            profit = Decimal(buy_token_in_native) - Decimal(sum_cost)
            if best_profit is None or profit > best_profit:
                best_profit = profit
                best_provider = provider
                best_price = price_response
        return best_provider, best_price

    async def get_meta_swap_quote(
        self,
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        taker_address: str,
        provider: str,
        chain_id: int,
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None,
    ) -> ProviderQuoteResponse:
        """
        Get a data for swap from a specific provider.

        Args:
            buy_token:str: Specify the token address that you want to buy
            sell_token:str: Specify the token address that is sold in the swap
            sell_amount:int: Specify the amount of tokens to sell in base units (e.g. 1 ETH = 10 ** 18)
            taker_address:str: Specify the address of the user who will be using this price_response
            provider:str: Specify the provider to use
            chain_id:int: Specify the chain on which to perform the swap
            gas_price:Optional[int]=None: Set the gas price for the transaction. If not set, the gas price will be fetched web3
            slippage_percentage:Optional[float]=None: Set a maximum percentage of slippage for the trade. (0.01 = 1%)
            fee_recipient:Optional[str]=None: Specify the address of a fee recipient
            buy_token_percentage_fee:Optional[float]=None: Specify a percentage of the buy_amount that will be used to pay fees

        Returns:
            ProviderQuoteResponse: The price_response object

        Raises:
            ProviderNotFound: If passed provider is not supported
            Type[BaseAggregationProviderError]: check utils/errors.py to get all possible errors
        """
        provider_name = provider

        provider = self.provider_registry.get(provider_name)
        if not provider:
            raise ProviderNotFound(provider)

        quote = await provider.get_swap_quote(
            buy_token=buy_token,
            sell_token=sell_token,
            sell_amount=sell_amount,
            chain_id=chain_id,
            gas_price=gas_price,
            slippage_percentage=slippage_percentage,
            taker_address=taker_address,
            fee_recipient=fee_recipient,
            buy_token_percentage_fee=buy_token_percentage_fee,
        )
        return quote

    async def get_provider_price(
        self,
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        chain_id: int,
        provider: str,
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = None,
        taker_address: Optional[str] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None,
    ) -> MetaPriceModel:
        """
        Get swap price from chosen provider.
        Works in the same way as get_swap_meta_price, but returns only one object.

        Args:
            buy_token:str: Specify the token address that you want to buy
            sell_token:str: Specify the token address that is sold in the swap
            sell_amount:int: Specify the amount of tokens to sell in base units (e.g. 1 ETH = 10 ** 18)
            chain_id:int: Specify the chain on which to perform the swap
            provider: Optional[str]: Specify the provider to use
            gas_price:Optional[int]=None: Set the gas price for the transaction. If not set, the gas price will be fetched web3
            slippage_percentage:Optional[float]=None: Set a maximum percentage of slippage for the trade. (0.01 = 1%)
            taker_address:str: Specify the address of the user who will be using this price_response
            fee_recipient:Optional[str]=None: Specify the address of a fee recipient
            buy_token_percentage_fee:Optional[float]=None: Specify a percentage of the buy_amount that will be used to pay fees

        Returns:
            MetaPriceModel object, which contain the following fields:
                provider:str: The name of the provider
                price_response:ProviderPriceResponse: The price_response from the provider
                approve_cost:int: The cost of the approve transaction
                is_allowed:bool: The user has enough allowance for the swap on this provider
                is_best:bool: Always None, because only one provider is used

        Raises:
            ProviderNotFound: If passed provider is not supported
            Type[BaseAggregationProviderError]: check utils/errors.py to get all possible errors
        """
        provider_instance = self.provider_registry.get(provider)
        if not provider:
            raise ProviderNotFound(provider)

        spender_address = next(
            (
                spender['address']
                for spender in self.providers.get_providers_on_chain(chain_id)[
                    'market_order'
                ]
                if spender['name'] == provider
            ),
            None,
        )

        web3_url = get_web3_url(chain_id, config=self.config)
        erc20_contract = Web3Client(web3_url, self.config).get_erc20_contract(
            sell_token
        )
        if not gas_price:
            gas_price = asyncio.create_task(
                self.gas_service.get_base_gas_price(chain_id)
            )
        allowance = await self.get_token_allowance(
            sell_token, spender_address, erc20_contract, taker_address
        )
        approve_cost = 0
        if allowance < sell_amount:
            approve_cost = await self.get_approve_cost(
                owner_address=taker_address,
                spender_address=spender_address,
                erc20_contract=erc20_contract,
            )
        gas_price = (
            await gas_price if isinstance(gas_price, asyncio.Task) else gas_price
        )
        price = await provider_instance.get_swap_price(
            buy_token=buy_token,
            sell_token=sell_token,
            sell_amount=sell_amount,
            chain_id=chain_id,
            gas_price=gas_price,
            slippage_percentage=slippage_percentage,
            taker_address=taker_address,
            fee_recipient=fee_recipient,
            buy_token_percentage_fee=buy_token_percentage_fee,
        )
        return MetaPriceModel(
            provider=provider,
            price_response=price,
            is_allowed=bool(allowance),
            approve_cost=approve_cost,
        )

    async def get_crosschain_meta_swap_quote(
        self,
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        taker_address: str,
        provider: str,
        chain_id_from: int,
        chain_id_to: int,
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None,
    ) -> ProviderQuoteResponse:
        """
        Get a data for crosschain swap from a specific provider.

        Args:
            buy_token:str: Specify the token address that you want to buy
            sell_token:str: Specify the token address that is sold in the swap
            sell_amount:int: Specify the amount of tokens to sell in base units (e.g. 1 ETH = 10 ** 18)
            taker_address:str: Specify the address of the user who will be using this price_response
            provider:str: Specify the provider to use
            chain_id_from:int: Specify the chain on which the transaction will be executed, a chain where the cross-chain swap will start
            chain_id_to:int: chain where the cross-chain swap will finish
            gas_price:Optional[int]=None: Set the gas price for the transaction. If not set, the gas price will be fetched web3
            slippage_percentage:Optional[float]=None: Set a maximum percentage of slippage for the trade. (0.01 = 1%)
            fee_recipient:Optional[str]=None: Specify the address of a fee recipient
            buy_token_percentage_fee:Optional[float]=None: Specify a percentage of the buy_amount that will be used to pay fees

        Returns:
            ProviderQuoteResponse: The price_response object

        Raises:
            ProviderNotFound: If passed provider is not supported
            Type[BaseAggregationProviderError]: check utils/errors.py to get all possible errors
        """
        provider_name = provider

        provider = self.provider_registry.get(provider_name)
        if not provider:
            raise ProviderNotFound(provider)

        quote = await provider.get_swap_quote(
            buy_token=buy_token,
            sell_token=sell_token,
            sell_amount=sell_amount,
            chain_id_from=chain_id_from,
            chain_id_to=chain_id_to,
            gas_price=gas_price,
            slippage_percentage=slippage_percentage,
            taker_address=taker_address,
            fee_recipient=fee_recipient,
            buy_token_percentage_fee=buy_token_percentage_fee,
        )
        return quote

    async def get_crosschain_provider_price(
        self,
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        chain_id_from: int,
        chain_id_to: int,
        provider: str,
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = None,
        taker_address: Optional[str] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None,
    ) -> MetaPriceModel:
        """
        Get crosschain swap price from chosen provider.
        Works in the same way as get_swap_meta_price, but returns only one object.

        Args:
            buy_token:str: Specify the token address that you want to buy
            sell_token:str: Specify the token address that is sold in the swap
            sell_amount:int: Specify the amount of tokens to sell in base units (e.g. 1 ETH = 10 ** 18)
            chain_id_from:int: Specify the chain on which the transaction will be executed, a chain where the cross-chain swap will start
            chain_id_to:int: chain where the cross-chain swap will finish
            provider: Optional[str]: Specify the provider to use
            gas_price:Optional[int]=None: Set the gas price for the transaction. If not set, the gas price will be fetched web3
            slippage_percentage:Optional[float]=None: Set a maximum percentage of slippage for the trade. (0.01 = 1%)
            taker_address:str: Specify the address of the user who will be using this price_response
            fee_recipient:Optional[str]=None: Specify the address of a fee recipient
            buy_token_percentage_fee:Optional[float]=None: Specify a percentage of the buy_amount that will be used to pay fees

        Returns:
            MetaPriceModel object, which contain the following fields:
                provider:str: The name of the provider
                price_response:ProviderPriceResponse: The price_response from the provider
                approve_cost:int: The cost of the approve transaction
                is_allowed:bool: The user has enough allowance for the swap on this provider
                is_best:bool: Always None, because only one provider is used

        Raises:
            ProviderNotFound: If passed provider is not supported
            Type[BaseAggregationProviderError]: check utils/errors.py to get all possible errors
        """
        provider_instance: CrossChainProvider = self.provider_registry.get(provider)
        if not provider_instance:
            raise ProviderNotFound(provider)

        if provider_instance.is_require_gas_price():
            if not gas_price:
                gas_price = asyncio.create_task(
                    self.gas_service.get_base_gas_price(chain_id_from)
                )
            gas_price = (
                await gas_price if isinstance(gas_price, asyncio.Task) else gas_price
            )

        price = await provider_instance.get_swap_price(
            buy_token=buy_token,
            sell_token=sell_token,
            sell_amount=sell_amount,
            chain_id_from=chain_id_from,
            chain_id_to=chain_id_to,
            gas_price=gas_price,
            slippage_percentage=slippage_percentage,
            taker_address=taker_address,
            fee_recipient=fee_recipient,
            buy_token_percentage_fee=buy_token_percentage_fee,
        )

        web3_url = get_web3_url(chain_id_from, config=self.config)
        erc20_contract = Web3Client(web3_url, self.config).get_erc20_contract(
            sell_token
        )

        approve_cost = 0
        if price.allowance_target is None:
            spender_address = next(
                (
                    spender['address']
                    for spender in self.providers.get_providers_on_chain(chain_id_from)[
                        'market_order'
                    ]
                    if spender['name'] == provider
                ),
                None,
            )

        else:
            spender_address = price.allowance_target

        allowance = await self.get_token_allowance(
            sell_token, spender_address, erc20_contract, taker_address
        )
        if allowance < sell_amount:
            approve_cost = await self.get_approve_cost(
                owner_address=taker_address,
                spender_address=spender_address,
                erc20_contract=erc20_contract,
            )

        return MetaPriceModel(
            provider=provider,
            price_response=price,
            is_allowed=bool(allowance),
            approve_cost=approve_cost,
        )
