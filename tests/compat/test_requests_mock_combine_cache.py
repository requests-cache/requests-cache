"""Example of using requests-cache with the requests-mock library"""
import pytest
from requests_mock import Adapter
from requests_cache import CachedSession

URL = 'https://some_test_url'


@pytest.fixture(scope='function')
def mock_session():
    """Fixture that provides a CachedSession that will make mock requests where it would normally
    make real requests"""
    adapter = Adapter()
    adapter.register_uri(
        'GET',
        URL,
        headers={'Content-Type': 'text/plain'},
        text='Mock response!',
        status_code=200,
    )

    session = CachedSession(backend='memory')
    session.mount('https://', adapter)
    yield session


def test_mock_session(mock_session):
    """Test that the mock_session fixture is working as expected"""
    response_1 = mock_session.get(URL)
    assert response_1.text == 'Mock response!'
    assert getattr(response_1, 'from_cache', False) is False

    response_2 = mock_session.get(URL)
    assert response_2.text == 'Mock response!'
    assert response_2.from_cache is True
