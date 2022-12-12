from aiohttp import ClientResponseError, RequestInfo

from utils.errors import ParseResponseError, AggregationProviderError


def test_handle_exception_key_error(zerox_provider, caplog):
    exc = zerox_provider.handle_exception(KeyError('test'))
    assert caplog.text
    assert caplog.handler.records[0].module == 'base_provider'
    assert isinstance(exc, ParseResponseError)


def test_handle_exception_client_response_error(zerox_provider, caplog):
    exc = zerox_provider.handle_exception(ClientResponseError(
        RequestInfo(url='abc', method='GET', headers=None), None, message='not enough allowance'))
    assert caplog.text
    assert isinstance(exc, AggregationProviderError)
