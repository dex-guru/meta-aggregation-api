import asyncio
from decimal import Decimal
from time import time
from typing import Optional, Tuple, List

from clients.blockchain.evm import EVMBase
from models.meta_agg_models import MetaPriceModel
from models.provider_response_models import SwapPriceResponse
from utils.node import find_most_synced_node_in_pool
from web3 import Web3
from web3.contract import Contract

from clients.blockchain.custom_http_provider import CustomHTTPProvider
from config import config
from provider_clients.one_inch_provider import OneInchProvider
from provider_clients.paraswap_provider import ParaSwapProvider
from provider_clients.zerox_provider import ZeroXProvider
from utils.async_utils import async_from_sync
from utils.errors import ProviderNotFound, SpenderAddressNotFound
from utils.logger import get_logger

PROVIDERS = {
    AggregationProviderChoices.zero_x: ZeroXProvider,
    AggregationProviderChoices.one_inch: OneInchProvider,
    AggregationProviderChoices.paraswap: ParaSwapProvider,
}

logger = get_logger(__name__)


@async_from_sync
def get_token_allowance(
        token_address: str,
        spender_address: str,
        erc20_contract: Contract,
        owner_address: Optional[str] = None,
) -> int:
    logger.debug('Getting allowance for token %s', token_address)
    if token_address == config.NATIVE_TOKEN_ADDRESS:
        return 2 ** 256 - 1
    owner_address = Web3.toChecksumAddress(owner_address)
    spender_address = Web3.toChecksumAddress(spender_address)
    token_address = Web3.toChecksumAddress(token_address)
    allowance = erc20_contract.functions.allowance(owner_address, spender_address).call({'to': token_address})
    return allowance


@async_from_sync
def get_approve_cost(
        owner_address: str,
        spender_address: str,
        erc20_contract: Contract,
) -> int:
    logger.debug('Getting approve cost for owner %s', owner_address)
    owner_address = Web3.toChecksumAddress(owner_address)
    spender_address = Web3.toChecksumAddress(spender_address)
    approve_cost = erc20_contract.functions.approve(spender_address, 2 ** 256 - 1).estimate_gas({'from': owner_address})
    return approve_cost


async def get_approve_costs_per_provider(
        network: str,
        sell_token: str,
        erc20_contract: Contract,
        sell_amount: int,
        providers: list,
        taker_address: Optional[str] = None,
) -> dict:
    logger.debug('Getting approve costs for network %s', network)
    approve_costs_per_provider = {}
    for provider in providers:
        if not taker_address:
            approve_costs_per_provider[provider['provider']] = 0
            continue
        spender_address = provider['address']
        allowance = await get_token_allowance(sell_token, spender_address, erc20_contract, taker_address)
        logger.info('Got allowance for token %s: %s', sell_token, allowance,
                    extra={
                        'taker_address': taker_address,
                        'spender_address': spender_address,
                        'token_address': sell_token,
                    })

        if allowance < sell_amount:
            logger.debug('Allowance is not enough, getting approve cost')
            approve_cost = await get_approve_cost(taker_address, spender_address, erc20_contract)
            approve_costs_per_provider[provider['provider']] = approve_cost
        else:
            approve_costs_per_provider[provider['provider']] = 0
    return approve_costs_per_provider


async def get_base_gas_price(network: Optional[str], web3_url: Optional[str] = None) -> int:
    logger.debug('Getting gas prices for network %s', network)
    if not web3_url and not network:
        raise ValueError('Either network or web3_url must be provided')
    if not web3_url:
        web3_url = await find_most_synced_node_in_pool(logger, get_chain_id_by_network(network))
    w3 = Web3(CustomHTTPProvider(endpoint_uri=web3_url))
    gas_price = w3.eth.gas_price
    logger.info('Gas price for network %s is %s', network, gas_price)
    return gas_price


async def get_swap_meta_price(
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        network: NetworkChoices,
        affiliate_address: Optional[str] = None,
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = None,
        taker_address: Optional[str] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None,
        spender_addresses: Optional[list[dict]] = None,
) -> List[MetaPriceModel]:
    web3_url = await find_most_synced_node_in_pool(logger, get_chain_id_by_network(network))
    erc20_contract = EVMBase(web3_url).get_erc20_contract(Web3.toChecksumAddress(sell_token))
    approve_costs = asyncio.create_task(get_approve_costs_per_provider(network, sell_token, erc20_contract,
                                                                       sell_amount, spender_addresses, taker_address))
    get_decimals_task = asyncio.create_task(get_decimals_for_native_and_buy_token(network, buy_token))
    get_buy_token_price_task = asyncio.create_task(CandleService().get_price_from_candle_by_ts(
        buy_token, network, time(), CurrencyChoices.native,
    ))
    if not gas_price:
        gas_price = await get_base_gas_price(network, web3_url)

    quotes_tasks = []
    for provider in spender_addresses:
        if provider is None:
            continue
        provider_name = provider['provider']
        provider_class = PROVIDERS.get(provider_name)
        if not provider_class:
            continue
        provider_instance = provider_class()
        quotes_tasks.append(asyncio.create_task(provider_instance.get_swap_price(
            buy_token, sell_token, sell_amount, network,
            affiliate_address, gas_price, slippage_percentage, taker_address,
            fee_recipient, buy_token_percentage_fee,
        )))
    quotes_list = await asyncio.gather(*quotes_tasks, return_exceptions=True)
    quotes = {quote.provider: quote for quote in quotes_list if
              isinstance(quote, SwapPriceResponse)}  # {provider: quote}
    if not any(quotes):
        logger.error(
            'No prices found',
            extra={
                'buy_token': buy_token,
                'sell_token': sell_token,
                'sell_amount': sell_amount,
                'network': network,
                'providers': list(quotes.keys()),
            }
        )
        raise ValueError('No prices found')
    approve_costs = await approve_costs
    native_decimals, buy_token_decimals = await get_decimals_task
    buy_token_price = await get_buy_token_price_task
    best_provider, quote = choose_best_provider(quotes, approve_costs, native_decimals, buy_token_decimals,
                                                buy_token_price)
    logger.info(
        'Got swap prices for network %s', network,
        extra={
            'best_provider': best_provider,
            'buy_token': buy_token,
            'sell_token': sell_token,
            'taker_address': taker_address,
        }
    )
    return [
        MetaPriceModel(provider=provider_, is_allowed=approve_costs[provider_] == 0,
                       quote=quote, is_best=provider_ == best_provider, approve_cost=approve_costs[provider_])
        for provider_, quote in quotes.items()
    ]


async def get_decimals_for_native_and_buy_token(network: NetworkChoices, buy_token: str) -> Tuple[int, int]:
    wrapped_native_for_network = NativeTokenAddresses[network].value
    logger.debug('Getting decimals for native %s and buy tokens %s', wrapped_native_for_network, buy_token)
    erc20_token_inv_service = ERC20TokensService()
    if buy_token == config.NATIVE_TOKEN_ADDRESS or buy_token == wrapped_native_for_network:
        buy_token_inventory = await erc20_token_inv_service.get_erc20_token_by_address_network(
            wrapped_native_for_network, network)
        buy_token_decimals = buy_token_inventory.decimals
        native_decimals = buy_token_decimals
    else:
        buy_token_inventory, native_token_inventory = await asyncio.gather(
            erc20_token_inv_service.get_erc20_token_by_address_network(buy_token, network),
            erc20_token_inv_service.get_erc20_token_by_address_network(
                wrapped_native_for_network, network))
        buy_token_decimals = buy_token_inventory.decimals
        native_decimals = native_token_inventory.decimals
    logger.debug('Got decimals for native %s and buy tokens %s', wrapped_native_for_network, buy_token)
    return native_decimals, buy_token_decimals


def choose_best_provider(
        quotes: dict,
        approve_costs: dict,
        native_decimals: int,
        buy_token_decimals: int,
        buy_token_price: float,
) -> Tuple[AggregationProviderChoices, MetaSwapPriceResponse]:
    best_provider = None
    best_quote = None
    best_profit = None
    buy_token_price = Decimal(str(buy_token_price))
    for provider, quote in quotes.items():
        if not quote:
            continue
        cost = Decimal(quote.gas) * Decimal(quote.gasPrice) + Decimal(approve_costs[provider]) * Decimal(quote.gasPrice)
        cost_amount = Decimal(cost) / 10 ** native_decimals
        buy_token_amount = Decimal(quote.buyAmount) / 10 ** buy_token_decimals
        buy_token_in_native = buy_token_amount * buy_token_price
        profit = Decimal(buy_token_in_native) - Decimal(cost_amount)
        if best_profit is None or profit > best_profit:
            best_profit = profit
            best_provider = provider
            best_quote = quote
    return best_provider, best_quote


async def get_meta_swap_quote(
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        taker_address: str,
        provider: AggregationProviderChoices,
        network: NetworkChoices,
        affiliate_address: Optional[str],
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None,
):
    provider_class = PROVIDERS.get(provider)
    if not provider_class:
        return
    provider = provider_class()
    quote = await provider.get_swap_quote(
        buy_token=buy_token,
        sell_token=sell_token,
        sell_amount=sell_amount,
        network=network,
        affiliate_address=affiliate_address,
        gas_price=gas_price,
        slippage_percentage=slippage_percentage,
        taker_address=taker_address,
        fee_recipient=fee_recipient,
        buy_token_percentage_fee=buy_token_percentage_fee,
    )
    return quote


async def get_provider_price(
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        network: NetworkChoices,
        provider: Optional[AggregationProviderChoices],
        affiliate_address: Optional[str] = None,
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = None,
        taker_address: Optional[str] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None,
        spender_addresses: Optional[list[dict]] = None,
) -> MetaPriceModel:
    provider_class = PROVIDERS.get(provider)
    if not provider_class:
        raise ProviderNotFound(provider)

    spender_address = next((spender['address'] for spender in spender_addresses if spender['provider'] == provider),
                           None)
    if not spender_address:
        raise SpenderAddressNotFound(provider)
    provider_instance = provider_class()

    web3_url = await find_most_synced_node_in_pool(logger, get_chain_id_by_network(network))
    erc20_contract = EVMBase(web3_url).get_erc20_contract(Web3.toChecksumAddress(sell_token))
    if not gas_price:
        gas_price = asyncio.create_task(get_base_gas_price(network, web3_url))
    allowance = await get_token_allowance(sell_token, spender_address, erc20_contract, taker_address)
    approve_cost = 0
    if allowance < sell_amount:
        approve_cost = await get_approve_cost(
            owner_address=taker_address,
            spender_addresses=spender_addresses,
            erc20_contract=erc20_contract,
        )
    gas_price = await gas_price if isinstance(gas_price, asyncio.Task) else gas_price
    price = await provider_instance.get_swap_price(
        buy_token, sell_token, sell_amount, network,
        affiliate_address, gas_price, slippage_percentage, taker_address,
        fee_recipient, buy_token_percentage_fee,
    )
    return MetaPriceModel(provider=provider, quote=price,
                          is_allowed=bool(allowance), approve_cost=approve_cost)
