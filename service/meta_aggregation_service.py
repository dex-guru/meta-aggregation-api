import asyncio
from decimal import Decimal
from typing import Optional, Tuple, List

from dexguru_sdk import DexGuru
from web3 import Web3
from web3.contract import AsyncContract

from clients.blockchain.web3_client import Web3Client
from config import config, chains
from config.providers import providers
from models.meta_agg_models import MetaPriceModel, MetaSwapPriceResponse
from provider_clients.one_inch_provider import OneInchProvider
from provider_clients.paraswap_provider import ParaSwapProvider
from provider_clients.zerox_provider import ZeroXProvider
from service.gas_service import get_base_gas_price
from utils.common import get_web3_url
from utils.errors import ProviderNotFound, SpenderAddressNotFound
from utils.logger import get_logger


class Providers:
    zero_x = ZeroXProvider
    one_inch = OneInchProvider
    paraswap = ParaSwapProvider

    @classmethod
    def get(cls, provider_name: str):
        return getattr(cls, provider_name, None)


logger = get_logger(__name__)


# TODO: check if async Web 3 can work for us @Safrankov have exp
async def get_token_allowance(
        token_address: str,
        spender_address: str,
        erc20_contract: AsyncContract,
        owner_address: Optional[str] = None,
) -> int:
    logger.debug('Getting allowance for token %s', token_address)
    if token_address == config.NATIVE_TOKEN_ADDRESS or not owner_address:
        return 2 ** 256 - 1
    owner_address = Web3.toChecksumAddress(owner_address)
    spender_address = Web3.toChecksumAddress(spender_address)
    token_address = Web3.toChecksumAddress(token_address)
    allowance = await erc20_contract.functions.allowance(owner_address, spender_address).call({'to': token_address})
    return allowance


# TODO: check if async Web 3 can work for us @Safrankov have exp
async def get_approve_cost(
        owner_address: str,
        spender_address: str,
        erc20_contract: AsyncContract,
) -> int:
    logger.debug('Getting approve cost for owner %s', owner_address)
    owner_address = Web3.toChecksumAddress(owner_address)
    spender_address = Web3.toChecksumAddress(spender_address)
    approve_cost = await erc20_contract.functions.approve(spender_address, 2 ** 256 - 1).estimate_gas(
        {'from': owner_address})
    return approve_cost


async def get_approve_costs_per_provider(
        sell_token: str,
        erc20_contract: AsyncContract,
        sell_amount: int,
        providers: list,
        taker_address: Optional[str] = None,
) -> dict:
    # TODO: descriprtion of approval problem
    approve_costs_per_provider = {}
    for provider in providers:
        if not taker_address:
            approve_costs_per_provider[provider['name']] = 0
            continue
        spender_address = provider['address']
        allowance = await get_token_allowance(sell_token, spender_address, erc20_contract, taker_address)
        logger.debug('Got allowance for token %s: %s', sell_token, allowance)
        if allowance < sell_amount:
            logger.debug('Allowance is not enough, getting approve cost')
            approve_cost = await get_approve_cost(taker_address, spender_address, erc20_contract)
            approve_costs_per_provider[provider['name']] = approve_cost
        else:
            approve_costs_per_provider[provider['name']] = 0
    return approve_costs_per_provider


# TODO: cache?, partially at least
async def get_swap_meta_price(
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        chain_id: int,
        affiliate_address: Optional[str] = None,
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = None,
        taker_address: Optional[str] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None,
) -> List[MetaPriceModel]:
    # TODO: Add description, app.config?
    spender_addresses = providers.get(chain_id)['market_order']
    web3_url = get_web3_url(chain_id)
    erc20_contract = Web3Client(web3_url).get_erc20_contract(Web3.toChecksumAddress(sell_token))
    approve_costs = asyncio.create_task(get_approve_costs_per_provider(sell_token, erc20_contract,
                                                                       sell_amount, spender_addresses, taker_address))
    get_decimals_task = asyncio.create_task(get_decimals_for_native_and_buy_token(chain_id, buy_token))
    get_buy_token_price_task = asyncio.create_task(DexGuru(config.API_KEY).get_token_finance(chain_id, buy_token))
    if not gas_price:
        gas_price = await get_base_gas_price(chain_id)

    quotes_tasks = []
    for provider in spender_addresses:
        if provider is None:
            continue
        provider_name = provider['name']
        provider_class = Providers.get(provider_name)
        if not provider_class:
            continue
        provider_instance = provider_class()
        quotes_tasks.append(asyncio.create_task(provider_instance.get_swap_price(
            buy_token, sell_token, sell_amount, chain_id,
            affiliate_address, gas_price, slippage_percentage, taker_address,
            fee_recipient, buy_token_percentage_fee,
        )))
    quotes_list = await asyncio.gather(*quotes_tasks, return_exceptions=True)
    quotes = {quote.provider: quote for quote in quotes_list if
              isinstance(quote, MetaSwapPriceResponse)}  # {provider: quote}
    if not any(quotes):
        logger.error(
            'No prices found',
            extra={'buy_token': buy_token, 'sell_token': sell_token, 'sell_amount': sell_amount,
                   'chain_id': chain_id, 'providers': list(quotes.keys())}
        )
        raise ValueError('No prices found')
    approve_costs = await approve_costs
    native_decimals, buy_token_decimals = await get_decimals_task
    buy_token_price = await get_buy_token_price_task
    buy_token_price = buy_token_price.price_eth
    best_provider, quote = choose_best_provider(quotes, approve_costs, native_decimals, buy_token_decimals,
                                                buy_token_price)
    logger.info(
        'Got swap prices for chain %s', chain_id,
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


async def get_decimals_for_native_and_buy_token(chain_id: int, buy_token: str) -> Tuple[int, int]:
    # TODO: add description
    wrapped_native = chains.get_chain_by_id(chain_id).native_token
    native_decimals = wrapped_native.decimals
    guru_sdk = DexGuru(config.API_KEY)
    if buy_token == config.NATIVE_TOKEN_ADDRESS or buy_token == wrapped_native:
        buy_token_decimals = native_decimals
    else:
        buy_token_inventory = await guru_sdk.get_token_inventory_by_address(chain_id, buy_token)
        buy_token_decimals = buy_token_inventory.decimals
    return native_decimals, buy_token_decimals


def choose_best_provider(
        quotes: dict,
        approve_costs: dict,
        native_decimals: int,
        buy_token_decimals: int,
        buy_token_price: float,
) -> Tuple[str, MetaSwapPriceResponse]:
    # TODO: Formula description
    best_provider = None
    best_quote = None
    best_profit = None
    buy_token_price = Decimal(str(buy_token_price))
    for provider, quote in quotes.items():
        if not quote:
            continue
        cost = Decimal(quote.gas) * Decimal(quote.gas_price) + Decimal(approve_costs[provider]) * Decimal(
            quote.gas_price)
        cost_amount = Decimal(cost) / 10 ** native_decimals
        buy_token_amount = Decimal(quote.buy_amount) / 10 ** buy_token_decimals
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
        provider: str,
        chain_id: int,
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None,
):
    # TODO: Add description
    provider_class = Providers.get(provider)
    if not provider_class:
        return
    provider = provider_class()
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
        buy_token: str,
        sell_token: str,
        sell_amount: int,
        chain_id: int,
        provider: Optional[str],
        affiliate_address: Optional[str] = None,
        gas_price: Optional[int] = None,
        slippage_percentage: Optional[float] = None,
        taker_address: Optional[str] = None,
        fee_recipient: Optional[str] = None,
        buy_token_percentage_fee: Optional[float] = None,
) -> MetaPriceModel:
    provider_class = Providers.get(provider)
    if not provider_class:
        raise ProviderNotFound(provider)
    spender_address = next((spender['address'] for spender in providers.get(chain_id)['market_order']
                            if spender['name'] == provider), None)
    if not spender_address:
        raise SpenderAddressNotFound(provider)
    provider_instance = provider_class()

    web3_url = get_web3_url(chain_id)
    erc20_contract = Web3Client(web3_url).get_erc20_contract(sell_token)
    if not gas_price:
        gas_price = asyncio.create_task(get_base_gas_price(chain_id))
    allowance = await get_token_allowance(sell_token, spender_address, erc20_contract, taker_address)
    approve_cost = 0
    if allowance < sell_amount:
        approve_cost = await get_approve_cost(
            owner_address=taker_address,
            spender_address=spender_address,
            erc20_contract=erc20_contract,
        )
    gas_price = await gas_price if isinstance(gas_price, asyncio.Task) else gas_price
    price = await provider_instance.get_swap_price(
        buy_token, sell_token, sell_amount, chain_id,
        affiliate_address, gas_price, slippage_percentage, taker_address,
        fee_recipient, buy_token_percentage_fee,
    )
    return MetaPriceModel(provider=provider, quote=price,
                          is_allowed=bool(allowance), approve_cost=approve_cost)
