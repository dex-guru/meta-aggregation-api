from typing import List, Optional

from pydantic import BaseModel, Field

from meta_aggregation_api.models.provider_response_models import SwapSources


class ProviderPriceResponse(BaseModel):
    provider: str  # provider name. Set in provider class
    sources: List[SwapSources]  # list of liquidity sources for the swap
    buy_amount: str  # amount of buy_token to buy
    gas: str  # gas amount for the swap
    sell_amount: str  # amount of sell_token to sell
    gas_price: str  # gas price for the swap
    value: str  # amount of native token that should be sent with the transaction
    price: str  # price for buy_token in sell_token


class MetaPriceModel(BaseModel):
    provider: str  # provider name. Set in provider class
    price_response: ProviderPriceResponse  # price response object from provider
    is_allowed: bool  # if the provider has allowance to spend the sell_token of taker_address
    is_best: Optional[
        bool] = None  # none for request with one provider. True if the provider has the best price
    approve_cost: int = 0  # 0 for requests without taker_address. Cost of approve transaction for the provider


class ProviderQuoteResponse(BaseModel):
    sources: list  # list of liquidity sources for the swap
    buy_amount: str  # amount of buy_token to buy
    gas: str  # gas amount for the swap
    sell_amount: str  # amount of sell_token to sell
    to: str  # address where the swap will be executed
    data: str  # data for the swap
    gas_price: str  # gas price for the swap
    value: str  # amount of native token that should be sent with the transaction
    price: str  # price for buy_token in sell_token


class LimitOrderPostData(BaseModel):
    makerAsset: str = Field(
        ..., description='The address of maker token', alias='maker_asset'
    )
    takerAsset: str = Field(
        ..., description='The address of taker token', alias='taker_asset'
        )
    maker: str = Field(..., description='The address of maker')
    allowedSender: str = Field(
        ..., description='The address of allowed sender', alias='allowed_sender'
    )
    receiver: str = Field(..., description='The address of receiver')
    makingAmount: str = Field(
        ..., description='The amount of maker token', alias='making_amount'
    )
    takingAmount: str = Field(
        ..., description='The amount of taker token', alias='taking_amount')
    salt: str = Field(..., description='The salt of the order')
    interactions: Optional[str] = Field('0x', description='The interactions of the order')

    class Config:
        allow_population_by_field_name = True
