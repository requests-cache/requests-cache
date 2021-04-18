"""Fixtures that will be automatically picked up by pytest

Short description:
* The ``mock_session`` fixture uses pre-configured mock requests, and should be used for unit tests.
* The ``tempfile_session`` fixture makes real HTTP requests, and should be used for integration test.

Note: The protocol ``http(s)+mock://`` helps :py:class:`requests_mock.Adapter` play nicely with
:py:class:`requests.PreparedRequest`. More info here:
https://requests-mock.readthedocs.io/en/latest/adapter.html
"""
import os
import pytest
from functools import wraps
from logging import basicConfig, getLogger
from tempfile import NamedTemporaryFile

import requests
from requests_mock import ANY as ANY_METHOD
from requests_mock import Adapter
from timeout_decorator import timeout

import requests_cache
from requests_cache.session import ALL_METHODS, CachedSession

MOCKED_URL = 'http+mock://requests-cache.com/text'
MOCKED_URL_HTTPS = 'https+mock://requests-cache.com/text'
MOCKED_URL_JSON = 'http+mock://requests-cache.com/json'
MOCKED_URL_REDIRECT = 'http+mock://requests-cache.com/redirect'
MOCKED_URL_REDIRECT_TARGET = 'http+mock://requests-cache.com/redirect_target'
MOCK_PROTOCOLS = ['mock://', 'http+mock://', 'https+mock://']

# Configure logging to show debug output when tests fail (or with pytest -s)
basicConfig(level='INFO')
getLogger('requests_cache').setLevel('DEBUG')
logger = getLogger(__name__)


def httpbin(path):
    """Get the url for either a local or remote httpbin instance"""
    base_url = os.getenv('HTTPBIN_URL', 'http://localhost:80').rstrip('/')
    return f'{base_url}/{path}'


try:
    import pytest_httpbin  # noqa: F401

    USE_PYTEST_HTTPBIN = os.getenv('USE_PYTEST_HTTPBIN', '').lower() == 'true'
except ImportError:
    USE_PYTEST_HTTPBIN = False


@pytest.fixture(scope='session', autouse=USE_PYTEST_HTTPBIN)
def httpbin_wrapper(httpbin):
    """Allow pytest-httpbin to be used instead of the httpbin Docker container. This fixture does
    not need to be used manually. It will be autoused if both:
    * pytest-httpbin is installed
    * The environment variable USE_PYTEST_HTTPBIN is set to 'true'
    """
    logger.info('Using pytest-httpin for integration tests')
    os.environ['HTTPBIN_URL'] = httpbin.url
    return httpbin


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
            db_path=temp.name,
            backend='sqlite',
            allowable_methods=ALL_METHODS,
            suppress_warnings=True,
        )
        adapter = get_mock_adapter()
        for protocol in MOCK_PROTOCOLS:
            session.mount(protocol, adapter)
        session.mock_adapter = adapter
        yield session


@pytest.fixture(scope='function')
def tempfile_session() -> CachedSession:
    """Get a CachedSession using a temporary SQLite db"""
    with NamedTemporaryFile(suffix='.db') as temp:
        session = CachedSession(
            cache_name=temp.name,
            backend='sqlite',
            allowable_methods=ALL_METHODS,
            suppress_warnings=True,
        )
        yield session
    requests_cache.uninstall_cache()


@pytest.fixture(scope='function')
def installed_session() -> CachedSession:
    """Get a CachedSession using a temporary SQLite db, with global patching.
    Installs cache before test and uninstalls after.
    """
    with NamedTemporaryFile(suffix='.db') as temp:
        requests_cache.install_cache(
            cache_name=temp.name,
            backend='sqlite',
            allowable_methods=ALL_METHODS,
            suppress_warnings=True,
        )
        yield requests.Session()
    requests_cache.uninstall_cache()


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
    adapter.register_uri(
        ANY_METHOD,
        MOCKED_URL_REDIRECT,
        headers={'Content-Type': 'text/plain', 'Location': MOCKED_URL_REDIRECT_TARGET},
        text='mock redirect response',
        status_code=302,
    )
    adapter.register_uri(
        ANY_METHOD,
        MOCKED_URL_REDIRECT_TARGET,
        headers={'Content-Type': 'text/plain'},
        text='mock redirected response',
        status_code=200,
    )
    return adapter


def fail_if_no_connection(func) -> bool:
    """Decorator for testing a backend connection. This will intentionally cause a test failure if
    the wrapped function doesn't have dependencies installed, doesn't connect after a short timeout,
    or raises any exceptions.

    This allows us to fail quickly for backends that aren't set up, rather than hanging for an
    extended period of time.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            timeout(0.5)(func)(*args, **kwargs)
        except Exception as e:
            logger.error(e)
            pytest.fail('Could not connect to backend')

    return wrapper
