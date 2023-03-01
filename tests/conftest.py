"""Fixtures that will be automatically picked up by pytest

Short description:
* The ``mock_session`` fixture uses pre-configured mock requests, and should be used for unit tests.
* The ``tempfile_session`` fixture makes real HTTP requests, and should be used for integration tests.

Note: The protocol ``http(s)+mock://`` helps :py:class:`requests_mock.Adapter` play nicely with
:py:class:`requests.PreparedRequest`. More info here:
https://requests-mock.readthedocs.io/en/latest/adapter.html
"""
import os
import platform
import warnings
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import wraps
from importlib import import_module
from logging import basicConfig, getLogger
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
import requests
from requests import Request
from requests_mock import ANY as ANY_METHOD
from requests_mock import Adapter
from rich.logging import RichHandler
from timeout_decorator import timeout

from requests_cache import ALL_METHODS, CachedSession, install_cache, uninstall_cache

# Configure logging to show log output when tests fail (or with pytest -s)
basicConfig(
    level='INFO',
    format='%(message)s',
    datefmt='[%m-%d %H:%M:%S]',
    handlers=[RichHandler(rich_tracebacks=True, markup=True)],
)
# getLogger('requests_cache').setLevel('DEBUG')
logger = getLogger(__name__)


# Allow running longer stress tests with an environment variable
STRESS_TEST_MULTIPLIER = int(os.getenv('STRESS_TEST_MULTIPLIER', '1'))
N_WORKERS = 5 * STRESS_TEST_MULTIPLIER
N_ITERATIONS = 4 * STRESS_TEST_MULTIPLIER
N_REQUESTS_PER_ITERATION = 10 + 10 * STRESS_TEST_MULTIPLIER

HTTPBIN_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
HTTPBIN_FORMATS = [
    'brotli',
    'deflate',
    'deny',
    'encoding/utf8',
    'gzip',
    'html',
    'image/jpeg',
    'image/png',
    'image/svg',
    'image/webp',
    'json',
    'robots.txt',
    'xml',
]
HTTPDATE_STR = 'Fri, 16 APR 2021 21:13:00 GMT'
HTTPDATE_DATETIME = datetime(2021, 4, 16, 21, 13)
EXPIRED_DT = datetime.utcnow() - timedelta(1)
ETAG = '"644b5b0155e6404a9cc4bd9d8b1ae730"'
LAST_MODIFIED = 'Thu, 05 Jul 2012 15:31:30 GMT'

MOCKED_URL = 'http+mock://requests-cache.com/text'
MOCKED_URL_ETAG = 'http+mock://requests-cache.com/etag'
MOCKED_URL_HTTPS = 'https+mock://requests-cache.com/text'
MOCKED_URL_JSON = 'http+mock://requests-cache.com/json'
MOCKED_URL_REDIRECT = 'http+mock://requests-cache.com/redirect'
MOCKED_URL_REDIRECT_TARGET = 'http+mock://requests-cache.com/redirect_target'
MOCKED_URL_VARY = 'http+mock://requests-cache.com/vary'
MOCKED_URL_404 = 'http+mock://requests-cache.com/nonexistent'
MOCKED_URL_500 = 'http+mock://requests-cache.com/answer?q=this-statement-is-false'
MOCKED_URL_200_404 = 'http+mock://requests-cache.com/200-404'
MOCK_PROTOCOLS = ['mock://', 'http+mock://', 'https+mock://']

CACHE_NAME = 'pytest_cache'
PROJECT_DIR = Path(__file__).parent.parent.absolute()
SAMPLE_DATA_DIR = PROJECT_DIR / 'tests' / 'sample_data'
SAMPLE_CACHE_FILES = list(SAMPLE_DATA_DIR.glob('sample.db.*'))


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
def mock_session(tempfile_session) -> CachedSession:
    """Fixture for combining requests-cache with requests-mock. This will behave the same as a
    CachedSession, except it will make mock requests for ``mock://`` URLs, if it hasn't been cached
    already.

    For example, ``mock_session.get(MOCKED_URL)`` will return a mock response on the first call,
    and a cached mock response on the second call. Additional mock responses can be added via
    ``mock_session.mock_adapter.register_uri()``.

    This uses a temporary SQLite db stored in ``/tmp``, which will be removed after the fixture has
    exited.
    """
    yield mount_mock_adapter(tempfile_session)


@pytest.fixture(scope='function')
def tempfile_session(tempfile_path) -> CachedSession:
    """Get a CachedSession using a temporary SQLite db"""
    yield CachedSession(
        cache_name=tempfile_path,
        backend='sqlite',
        allowable_methods=ALL_METHODS,
    )


@pytest.fixture(scope='function')
def tempfile_path(tmpdir) -> str:
    """Get a unique tempfile path"""
    yield str(tmpdir / f'{uuid4()}.db')


@pytest.fixture(scope='function')
def installed_session(tempfile_path) -> CachedSession:
    """Get a CachedSession using a temporary SQLite db, with global patching.
    Installs cache before test and uninstalls after.
    """
    install_cache(
        cache_name=tempfile_path,
        backend='sqlite',
        allowable_methods=ALL_METHODS,
    )
    yield requests.Session()
    uninstall_cache()


def mount_mock_adapter(session: CachedSession) -> CachedSession:
    adapter = get_mock_adapter()
    for protocol in MOCK_PROTOCOLS:
        session.mount(protocol, adapter)
    session.mock_adapter = adapter
    return session


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
        MOCKED_URL_ETAG,
        headers={'ETag': ETAG},
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
    adapter.register_uri(
        ANY_METHOD,
        MOCKED_URL_VARY,
        headers={'Content-Type': 'text/plain', 'Vary': 'Accept'},
        text='mock response with Vary header',
        status_code=200,
    )
    adapter.register_uri(ANY_METHOD, MOCKED_URL_404, status_code=404)
    adapter.register_uri(ANY_METHOD, MOCKED_URL_500, status_code=500)
    adapter.register_uri(
        ANY_METHOD, MOCKED_URL_200_404, [{"status_code": 200}, {"status_code": 404}]
    )
    return adapter


def get_mock_response(
    method='GET',
    url='https://img.site.com/base/img.jpg',
    status_code=200,
    headers={},
    request_headers={},
):
    return MagicMock(
        url=url,
        status_code=status_code,
        headers=headers,
        request=Request(method=method, url=url, headers=request_headers),
    )


def assert_delta_approx_equal(dt1: datetime, dt2: datetime, target_delta, threshold_seconds=2):
    """Assert that the given datetimes are approximately ``target_delta`` seconds apart"""
    diff_in_seconds = (dt2 - dt1).total_seconds()
    assert abs(diff_in_seconds - target_delta) <= threshold_seconds


def fail_if_no_connection(connect_timeout: float = 1.0) -> bool:
    """Decorator for testing a backend connection. This will intentionally cause a test failure if
    the wrapped function doesn't have dependencies installed, doesn't connect after a short timeout,
    or raises any exceptions.

    This allows us to fail quickly for backends that aren't set up, rather than hanging for an
    extended period of time.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                timeout(connect_timeout, use_signals=False)(func)(*args, **kwargs)
            except Exception as e:
                logger.error(e)
                pytest.fail('Could not connect to backend')

        return wrapper

    return decorator


def is_installed(module_name: str) -> bool:
    """Check if a given dependency is installed"""
    try:
        import_module(module_name)
        return True
    except ImportError:
        return False


def skip_missing_deps(module_name: str) -> pytest.Mark:
    return pytest.mark.skipif(
        not is_installed(module_name), reason=f'{module_name} is not installed'
    )


@contextmanager
def ignore_deprecation():
    """Temporarily ilence deprecation warnings"""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', category=DeprecationWarning)
        yield


# Some tests must disable url normalization to retain the custom `http+mock://` protocol
patch_normalize_url = patch('requests_cache.cache_keys.normalize_url', side_effect=lambda x, y: x)

# TODO: Debug OperationalErrors with pypy
skip_pypy = pytest.mark.skipif(
    platform.python_implementation() == 'PyPy',
    reason='pypy-specific database locking issue',
)
