

def test_get_info(trading_client):
    response = trading_client.get('v1/info/0')
    assert response.status_code == 404
    assert response.json() == {'detail': 'Chain ID not found'}
