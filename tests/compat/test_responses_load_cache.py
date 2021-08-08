"""Example of using requests-cache with the responses library"""
from contextlib import contextmanager
from os.path import dirname, join
from unittest.mock import patch

import pytest
import requests
from responses import RequestsMock, Response
from requests.exceptions import ConnectionError
from requests_cache import CachedSession

TEST_DB = join(dirname(__file__), 'httpbin_sample.test-db')
TEST_URLS = [
    'https://httpbin.org/get',
    'https://httpbin.org/html',
    'https://httpbin.org/json',
]
PASSTHRU_URL = 'https://httpbin.org/gzip'
UNMOCKED_URL = 'https://httpbin.org/ip'


@contextmanager
def get_responses():
    """Contextmanager that provides a RequestsMock object mocked URLs and responses
    based on cache data
    """
    with RequestsMock() as mocker:
        cache = CachedSession(TEST_DB).cache
        for response in cache.values():
            mocker.add(
                Response(
                    response.request.method,
                    response.request.url,
                    body=response.content,
                    headers=response.headers,
                    status=response.status_code,
                )
            )
        mocker.add_passthru(PASSTHRU_URL)
        yield mocker


# responses patches HTTPAdapter.send(), so we need to patch one level lower to verify request mocking
@patch.object(
    requests.adapters.HTTPAdapter, 'get_connection', side_effect=ValueError('Real request made!')
)
def test_mock_session(mock_http_adapter):
    """Test that the mock_session fixture is working as expected"""
    with get_responses():
        # An error will be raised if a real request is made
        with pytest.raises(ValueError):
            requests.get(PASSTHRU_URL)

        # All mocked URLs will return a response based on requests-cache data
        for url in TEST_URLS:
            response = requests.get(url)
            assert getattr(response, 'from_cache', False) is False

        # responses will raise an error for an unmocked URL, as usual
        with pytest.raises(ConnectionError):
            requests.get(UNMOCKED_URL)
