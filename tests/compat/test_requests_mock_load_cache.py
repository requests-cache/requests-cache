"""Example of using requests-cache with the requests-mock library"""
from os.path import dirname, join
from unittest.mock import patch

import pytest

import requests
from requests import Session
from requests_cache import CachedSession
from requests_mock import Adapter, NoMockAddress

TEST_DB = join(dirname(__file__), 'httpbin_sample.test-db')
TEST_URLS = [
    'https://httpbin.org/get',
    'https://httpbin.org/html',
    'https://httpbin.org/json',
]
UNMOCKED_URL = 'https://httpbin.org/ip'


@pytest.fixture(scope='session')
def mock_session():
    """Fixture that provides a session with mocked URLs and responses based on cache data"""
    adapter = Adapter()
    cache = CachedSession(TEST_DB).cache

    for response in cache.values():
        adapter.register_uri(
            response.request.method,
            response.request.url,
            content=response.content,
            headers=response.headers,
            status_code=response.status_code,
        )
        print(f'Added mock response: {response}')

    session = Session()
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    yield session


@patch.object(requests.adapters.HTTPAdapter, 'send', side_effect=ValueError('Real request made!'))
def test_mock_session(mock_http_adapter, mock_session):
    """Test that the mock_session fixture is working as expected"""
    # An error will be raised if a real request is made
    with pytest.raises(ValueError):
        requests.get(TEST_URLS[0])

    # All mocked URLs will return a response based on requests-cache data
    for url in TEST_URLS:
        response = mock_session.get(url)
        assert getattr(response, 'from_cache', False) is False

    # requests-mock will raise an error for an unmocked URL, as usual
    with pytest.raises(NoMockAddress):
        mock_session.get(UNMOCKED_URL)


def save_test_data():
    """Run once to save data to reuse for tests, for demo purposes.
    In practice, you could just run your application or tests with requests-cache installed.
    """
    session = CachedSession(TEST_DB)
    for url in TEST_URLS:
        session.get(url)


if __name__ == '__main__':
    save_test_data()
