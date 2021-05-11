from requests.utils import default_headers

from requests_cache.models.response import CachedRequest
from tests.conftest import MOCKED_URL


def test_from_request(mock_session):
    response = mock_session.get(MOCKED_URL, data=b'mock request', headers={'foo': 'bar'})
    request = CachedRequest.from_request(response.request)
    expected_headers = {**default_headers(), 'Content-Length': '12', 'foo': 'bar'}

    assert response.request.body == request.body == b'mock request'
    assert response.request._cookies == request.cookies == {}
    assert response.request.headers == request.headers == expected_headers
    assert response.request.method == request.method == 'GET'
    assert response.request.url == request.url == MOCKED_URL
