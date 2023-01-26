def test_get_info(trading_client):
    response = trading_client.get('v1/info/0')
    assert response.status_code == 404
    assert response.json() == {'detail': 'Chain ID not found'}


def test_get_info_ok(trading_client):
    response = trading_client.get('v1/info')
    assert response.status_code == 200
    response_data = response.json()
    match response_data:
        case [{'chain_id': 1, 'limit_order': list(), 'market_order': list()}, *_]:
            pass
        case _:
            raise AssertionError(f'Unexpected response: {response_data}')
