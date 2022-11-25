from abc import abstractmethod

from fastapi import HTTPException

from utils.logger import LogArgs


class NotConfiguredError(Exception):
    """for not configured env variables"""


class UserServiceError(ValueError):
    """common error for users service"""


class UserServiceBadValueError(UserServiceError):
    """bad value error for users service"""
    # prepare for delete


class UserServiceBadSignatureError(UserServiceError):
    """bad signature error for users service"""
    # prepare for delete


class UserServiceBadCredentialsError(UserServiceError):
    """bad credentials error for users service"""
    # prepare for delete


class UserMistakes:
    code = 400
    error_owner = 'user'


class OurMistakes:
    code = 417
    error_owner = 'dexguru'


class ProviderMistakes:
    code = 409
    error_owner = 'provider'


class BaseAggregationProviderError(Exception):
    """common error for aggregation providers"""

    @property
    @abstractmethod
    def msg_to_log(self):
        ...

    @property
    @abstractmethod
    def code(self):
        ...

    @property
    @abstractmethod
    def error_owner(self):
        ...

    def __init__(self, provider: str, message: str = None, **kwargs):
        self.provider = provider
        self.message = message
        self.kwargs = kwargs

    def __str__(self):
        return f'{self.msg_to_log}. Source: {self.provider}'

    def __repr__(self):
        return f'{self.__class__.__name__}({self.provider}, {self.message}, {self.kwargs})'

    def to_dict(self):
        return {
            'provider': self.provider,
            'reason': self.message,
            'error_owner': self.error_owner,
            **self.kwargs,
        }

    def to_log_args(self):
        return (
            f'{self.msg_to_log.lower()}. Source: %({LogArgs.aggregation_provider})s',
            {LogArgs.aggregation_provider: self.provider}
        )

    def to_http_exception(self) -> HTTPException:
        return HTTPException(status_code=self.code, detail={
            'error': str(self),
            'reason': self.message,
            'provider': self.provider,
        })


class AggregationProviderError(ProviderMistakes, BaseAggregationProviderError):
    """common error for aggregation providers"""
    msg_to_log = 'Unhandeled error'


class EstimationError(UserMistakes, BaseAggregationProviderError):
    """Provider's API cannot estimate the swap price"""
    msg_to_log = 'Cannot estimate swap'


class InsufficientLiquidityError(ProviderMistakes, BaseAggregationProviderError):
    """Provider's API cannot find a liquidity for the swap"""
    msg_to_log = 'Cannot find a liquidity pools for swap'


class UserBalanceError(UserMistakes, BaseAggregationProviderError):
    """When user has not enough balance for swap"""
    msg_to_log = 'User has not enough balance'


class AllowanceError(UserMistakes, BaseAggregationProviderError):
    """When user has not enough allowance for swap"""
    msg_to_log = 'User has not enough allowance'


class ValidationFailedError(OurMistakes, BaseAggregationProviderError):
    """When some fields in requests are not valid"""
    msg_to_log = 'Swap validation failed'


class ParseResponseError(OurMistakes, BaseAggregationProviderError):
    """When provider's API returns invalid response, or we parse it wrong"""
    msg_to_log = 'Cannot parse response'


class TokensError(UserMistakes, BaseAggregationProviderError):
    """When user has not enough allowance for swap"""
    msg_to_log = 'Invalid tokens'


class PriceError(ProviderMistakes, BaseAggregationProviderError):
    """When provider cannot calculate token prices"""
    msg_to_log = 'Invalid price'


class ProviderTimeoutError(ProviderMistakes, BaseAggregationProviderError):
    """When provider does not respond in time"""
    msg_to_log = 'Provider is unavailable'


class ProviderNotFound(OurMistakes, BaseAggregationProviderError):
    """Provider's proxy class not found"""
    msg_to_log = 'Provider not found'


class SpenderAddressNotFound(OurMistakes, BaseAggregationProviderError):
    """Provider's spender address not found"""
    msg_to_log = 'Spender address not found'
