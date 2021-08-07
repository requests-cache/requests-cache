"""Example of using requests-cache with the requests-mock library"""
import pytest
import requests
import requests_cache


@pytest.fixture(scope='function')
def requests_cache_mock(requests_mock):
    with requests_cache.disabled():
        yield requests_mock


def test_requests_cache_mock(requests_cache_mock):
    """Within this test function, requests will be mocked and not cached"""
    url = 'https://example.com'
    requests_cache_mock.get(url, text='Mock response!')

    # Make sure the mocker is used
    response_1 = requests.get(url)
    assert response_1.text == 'Mock response!'

    # Make sure the cache is not used
    response_2 = requests.get(url)
    assert getattr(response_2, 'from_cache', False) is False
