"""Fixtures that will be automatically picked up by pytest

Note: The protocol ``http(s)+mock://`` helps :py:class:`requests_mock.Adapter` play nicely with
:py:class:`requests.PreparedRequest`. More info here:
https://requests-mock.readthedocs.io/en/latest/adapter.html
"""
import pytest
from tempfile import NamedTemporaryFile

from requests_mock import ANY as ANY_METHOD
from requests_mock import Adapter

from requests_cache import ALL_METHODS, CachedSession

MOCKED_URL = 'http+mock://requests-cache.com/text'
MOCKED_URL_GZIP = 'https+mock://requests-cache.com/gzip'  # TODO
MOCKED_URL_HTTPS = 'https+mock://requests-cache.com/text'
MOCKED_URL_JSON = 'http+mock://requests-cache.com/json'
MOCKED_URL_REDIRECT = 'http+mock://requests-cache.com/redirect'  # TODO
MOCK_PROTOCOLS = ['mock://', 'http+mock://', 'https+mock://']


@pytest.fixture(scope='function')
def mock_session() -> CachedSession:
    """Fixture for combining requests-cache with requests-mock. This will behave the same as a
    CachedSession, except it will make mock requests for ``mock://`` URLs, if it hasn't been cached
    already.

    For example, ``mock_session.get(MOCKED_URL)`` will return a mock response on the first call,
    and a cached mock response on the second call. Additional mock responses can be added via
    ``mock_session.mock_adapter.register_uri()``.

    This uses a temporary SQLite db stored in ``/tmp``, which will be removed after the fixture has
    exited.
    """
    with NamedTemporaryFile(suffix='.db') as temp:
        session = CachedSession(
            cache_name=temp.name,
            backend='sqlite',
            allowable_methods=ALL_METHODS,
            suppress_warnings=True,
        )
        adapter = get_mock_adapter()
        for protocol in MOCK_PROTOCOLS:
            session.mount(protocol, adapter)
        session.mock_adapter = adapter
        yield session


def get_mock_adapter() -> Adapter:
    """Get a requests-mock Adapter with some URLs mocked by default"""
    adapter = Adapter()
    adapter.register_uri(
        ANY_METHOD,
        MOCKED_URL,
        headers={'Content-Type': 'text/plain'},
        text='mock response',
        status_code=200,
    )
    adapter.register_uri(
        ANY_METHOD,
        MOCKED_URL_HTTPS,
        headers={'Content-Type': 'text/plain'},
        text='mock https response',
        status_code=200,
    )
    adapter.register_uri(
        ANY_METHOD,
        MOCKED_URL_JSON,
        headers={'Content-Type': 'application/json'},
        json={'message': 'mock json response'},
        status_code=200,
    )
    return adapter
