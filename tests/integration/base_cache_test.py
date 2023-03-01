"""Common tests to run for all backends (BaseCache subclasses)"""
import json
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime
from functools import partial
from io import BytesIO
from logging import getLogger
from random import randint
from time import sleep, time
from typing import Dict, Type
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
import requests
from requests import ConnectionError, PreparedRequest, Session

from requests_cache import ALL_METHODS, CachedResponse, CachedSession
from requests_cache.backends import BaseCache
from tests.conftest import (
    CACHE_NAME,
    ETAG,
    EXPIRED_DT,
    HTTPBIN_FORMATS,
    HTTPBIN_METHODS,
    HTTPDATE_STR,
    LAST_MODIFIED,
    N_ITERATIONS,
    N_REQUESTS_PER_ITERATION,
    N_WORKERS,
    USE_PYTEST_HTTPBIN,
    assert_delta_approx_equal,
    httpbin,
    skip_pypy,
)

logger = getLogger(__name__)


VALIDATOR_HEADERS = [{'ETag': ETAG}, {'Last-Modified': LAST_MODIFIED}]


class BaseCacheTest:
    """Base class for testing cache backend classes"""

    backend_class: Type[BaseCache] = None
    init_kwargs: Dict = {}

    def init_session(self, cache_name=CACHE_NAME, clear=True, **kwargs) -> CachedSession:
        kwargs = {**self.init_kwargs, **kwargs}
        kwargs.setdefault('allowable_methods', ALL_METHODS)
        backend = self.backend_class(cache_name, **kwargs)
        if clear:
            backend.clear()

        return CachedSession(backend=backend, **kwargs)

    @classmethod
    def teardown_class(cls):
        session = cls().init_session(clear=True)
        session.close()

    @pytest.mark.parametrize('method', HTTPBIN_METHODS)
    @pytest.mark.parametrize('field', ['params', 'data', 'json'])
    def test_all_methods(self, field, method, serializer=None):
        """Test all relevant combinations of methods X data fields.
        Requests with different request params, data, or json should be cached under different keys.

        Note: Serializer combinations are only tested for Filesystem backend.
        """
        url = httpbin(method.lower())
        session = self.init_session(serializer=serializer)
        for params in [{'param_1': 1}, {'param_1': 2}, {'param_2': 2}]:
            assert session.request(method, url, **{field: params}).from_cache is False
            assert session.request(method, url, **{field: params}).from_cache is True

    @pytest.mark.parametrize('response_format', HTTPBIN_FORMATS)
    def test_all_response_formats(self, response_format, serializer=None):
        """Test all relevant combinations of response formats X serializers"""
        session = self.init_session(serializer=serializer)
        # Workaround for this issue: https://github.com/kevin1024/pytest-httpbin/issues/60
        if response_format == 'json' and USE_PYTEST_HTTPBIN:
            session.settings.allowable_codes = (200, 404)

        r1 = session.get(httpbin(response_format))
        r2 = session.get(httpbin(response_format))
        assert r1.from_cache is False
        assert r2.from_cache is True

        # For JSON responses, variations like whitespace won't be preserved
        if r1.text.startswith('{'):
            assert r1.json() == r2.json()
        else:
            assert r1.content == r2.content

    def test_response_no_duplicate_read(self):
        """Ensure that response data is read only once per request, whether it's cached or not"""
        session = self.init_session()
        storage_class = type(session.cache.responses)

        # Patch storage class to track number of times getitem is called, without changing behavior
        with patch.object(
            storage_class, '__getitem__', side_effect=lambda k: CachedResponse()
        ) as getitem:
            session.get(httpbin('get'))
            assert getitem.call_count == 1

            session.get(httpbin('get'))
            assert getitem.call_count == 2

    @pytest.mark.parametrize('n_redirects', range(1, 5))
    @pytest.mark.parametrize('endpoint', ['redirect', 'absolute-redirect', 'relative-redirect'])
    def test_redirect_history(self, endpoint, n_redirects):
        """Test redirect caching (in separate `redirects` cache) with all types of redirect
        endpoints, using different numbers of consecutive redirects
        """
        session = self.init_session()
        session.get(httpbin(f'{endpoint}/{n_redirects}'))
        r2 = session.get(httpbin('get'))

        assert r2.from_cache is True
        assert len(session.cache.redirects) == n_redirects

    @pytest.mark.parametrize('endpoint', ['redirect', 'absolute-redirect', 'relative-redirect'])
    def test_redirect_responses(self, endpoint):
        """Test redirect caching (in main `responses` cache) with all types of redirect endpoints"""
        session = self.init_session(allowable_codes=(200, 302))
        r1 = session.head(httpbin(f'{endpoint}/2'))
        r2 = session.head(httpbin(f'{endpoint}/2'))

        assert r2.from_cache is True
        assert len(session.cache.redirects) == 0
        assert isinstance(r1.next, PreparedRequest) and r1.next.url.endswith('redirect/1')
        assert isinstance(r2.next, PreparedRequest) and r2.next.url.endswith('redirect/1')

    def test_cookies(self):
        session = self.init_session()

        def get_json(url):
            return json.loads(session.get(url).text)

        response_1 = get_json(httpbin('cookies/set/test1/test2'))
        with session.cache_disabled():
            assert get_json(httpbin('cookies')) == response_1

        # From cache
        response_2 = get_json(httpbin('cookies'))
        assert response_2 == get_json(httpbin('cookies'))

        # Not from cache
        with session.cache_disabled():
            response_3 = get_json(httpbin('cookies/set/test3/test4'))
            assert response_3 == get_json(httpbin('cookies'))

    @pytest.mark.parametrize(
        'cache_control, request_headers, expected_expiration',
        [
            (True, {}, 60),
            (True, {'Cache-Control': 'max-age=360'}, 60),
            (True, {'Cache-Control': 'no-store'}, None),
            (True, {'Expires': HTTPDATE_STR, 'Cache-Control': 'max-age=360'}, 60),
            (False, {}, None),
            (False, {'Cache-Control': 'max-age=360'}, 360),
            (False, {'Cache-Control': 'no-store'}, None),
            (False, {'Expires': HTTPDATE_STR, 'Cache-Control': 'max-age=360'}, 360),
        ],
    )
    def test_cache_control_expiration(self, cache_control, request_headers, expected_expiration):
        """Test cache headers for both requests and responses. The `/cache/{seconds}` endpoint returns
        Cache-Control headers, which should be used unless request headers are sent.
        No headers should be used if `cache_control=False`.
        """
        session = self.init_session(cache_control=cache_control)
        session.get(httpbin('cache/60'), headers=request_headers)
        response = session.get(httpbin('cache/60'), headers=request_headers)

        if expected_expiration is None:
            assert response.expires is None
        else:
            assert_delta_approx_equal(datetime.utcnow(), response.expires, expected_expiration)

    @pytest.mark.parametrize(
        'cached_response_headers, expected_from_cache',
        [
            ({}, False),
            ({'ETag': ETAG}, True),
            ({'Last-Modified': LAST_MODIFIED}, True),
            ({'ETag': ETAG, 'Last-Modified': LAST_MODIFIED}, True),
        ],
    )
    def test_conditional_request(self, cached_response_headers, expected_from_cache):
        """Test behavior of ETag and Last-Modified headers and 304 responses.

        When a cached response contains one of these headers, corresponding request headers should
        be added. The `/cache` endpoint returns a 304 if one of these request headers is present.
        When this happens, the previously cached response should be returned.
        """
        response = requests.get(httpbin('cache'))
        response.headers = cached_response_headers

        session = self.init_session(cache_control=True)
        session.cache.save_response(response, expires=EXPIRED_DT)

        response = session.get(httpbin('cache'))
        assert response.from_cache == expected_from_cache

    @pytest.mark.parametrize('validator_headers', VALIDATOR_HEADERS)
    @pytest.mark.parametrize(
        'cache_headers',
        [
            {'Cache-Control': 'max-age=0'},
            {'Cache-Control': 'max-age=0,must-revalidate'},
            {'Cache-Control': 'no-cache'},
            {'Expires': '0'},
        ],
    )
    def test_conditional_request__response_headers(self, cache_headers, validator_headers):
        """Test response headers that can initiate revalidation before a cached response expires"""
        url = httpbin('response-headers')
        response_headers = {**cache_headers, **validator_headers}
        session = self.init_session(cache_control=True)

        # This endpoint returns request params as response headers
        session.get(url, params=response_headers)

        # It doesn't respond to conditional requests, but let's just pretend it does
        with patch.object(Session, 'send', return_value=MagicMock(status_code=304)):
            response = session.get(url, params=response_headers)

        assert response.from_cache is True

    @pytest.mark.parametrize('validator_headers', VALIDATOR_HEADERS)
    @pytest.mark.parametrize('cache_headers', [{'Cache-Control': 'max-age=0'}])
    def test_conditional_request__refreshes_expire_date(self, cache_headers, validator_headers):
        """Test that revalidation attempt with 304 responses causes stale entry to become fresh again considering
        Cache-Control header of the 304 response."""
        url = httpbin('response-headers')
        first_response_headers = {**cache_headers, **validator_headers}
        session = self.init_session(cache_control=True)

        # This endpoint returns request params as response headers
        session.get(url, params=first_response_headers)

        # Add different Response Header to mocked return value of the session.send() function.
        updated_response_headers = {**first_response_headers, 'Cache-Control': 'max-age=60'}
        with patch.object(
            Session,
            'send',
            return_value=MagicMock(status_code=304, headers=updated_response_headers),
        ):
            response = session.get(url, params=first_response_headers)
        assert response.from_cache is True
        assert response.is_expired is False

        # Make sure an immediate subsequent request will be served from the cache for another max-age==60 secondss
        try:
            with patch.object(Session, 'send', side_effect=AssertionError):
                response = session.get(url, params=first_response_headers)
        except AssertionError:
            assert False, (
                "Session tried to perform re-validation although cached response should have been "
                "refreshened."
            )
        assert response.from_cache is True
        assert response.is_expired is False

    @pytest.mark.parametrize('stream', [True, False])
    def test_response_decode(self, stream):
        """Test that gzip-compressed raw responses (including streamed responses) can be manually
        decompressed with decode_content=True
        """
        session = self.init_session()
        response = session.get(httpbin('gzip'), stream=stream)
        assert b'gzipped' in response.content
        if stream is True:
            assert b'gzipped' in response.raw.read(None, decode_content=True)
        response.raw._fp = BytesIO(response.content)

        cached_response = CachedResponse.from_response(response)
        assert b'gzipped' in cached_response.content
        assert b'gzipped' in cached_response.raw.read(None, decode_content=True)

    def test_multipart_upload(self):
        session = self.init_session()
        session.post(httpbin('post'), files={'file1': BytesIO(b'10' * 1024)})
        for i in range(5):
            assert session.post(httpbin('post'), files={'file1': BytesIO(b'10' * 1024)}).from_cache

    def test_delete__expired(self):
        session = self.init_session(expire_after=1)

        # Populate the cache with several responses that should expire immediately
        for response_format in HTTPBIN_FORMATS:
            session.get(httpbin(response_format))
        session.get(httpbin('redirect/1'))
        sleep(1)

        # Cache a response and some redirects, which should be the only non-expired cache items
        session.get(httpbin('get'), expire_after=-1)
        session.get(httpbin('redirect/3'), expire_after=-1)
        assert len(session.cache.redirects.keys()) == 4
        session.cache.delete(expired=True)

        assert len(session.cache.responses.keys()) == 2
        assert len(session.cache.redirects.keys()) == 3
        assert not session.cache.contains(url=httpbin('redirect/1'))
        assert not any([session.cache.contains(url=httpbin(f)) for f in HTTPBIN_FORMATS])

    @pytest.mark.parametrize('method', HTTPBIN_METHODS)
    def test_filter_request_headers(self, method):
        url = httpbin(method.lower())
        session = self.init_session(ignored_parameters=['Authorization'])
        response = session.request(method, url, headers={"Authorization": "<Secret Key>"})
        assert response.from_cache is False
        response = session.request(method, url, headers={"Authorization": "<Secret Key>"})
        assert response.from_cache is True
        assert response.request.headers.get('Authorization') == 'REDACTED'

    @pytest.mark.parametrize('method', HTTPBIN_METHODS)
    def test_filter_request_query_parameters(self, method):
        url = httpbin(method.lower())
        session = self.init_session(ignored_parameters=['api_key'])
        response = session.request(method, url, params={"api_key": "<Secret Key>"})
        assert response.from_cache is False
        response = session.request(method, url, params={"api_key": "<Secret Key>"})
        assert response.from_cache is True
        query = urlparse(response.request.url).query
        query_dict = parse_qs(query)
        assert query_dict['api_key'] == ['REDACTED']

    @skip_pypy
    @pytest.mark.parametrize('post_type', ['data', 'json'])
    def test_filter_request_post_data(self, post_type):
        method = 'POST'
        url = httpbin(method.lower())
        body = {"api_key": "<Secret Key>"}
        headers = {}
        if post_type == 'data':
            body = json.dumps(body)
            headers = {'Content-Type': 'application/json'}
        session = self.init_session(ignored_parameters=['api_key'])

        response = session.request(method, url, headers=headers, **{post_type: body})
        response = session.request(method, url, headers=headers, **{post_type: body})
        assert response.from_cache is True

        parsed_body = json.loads(response.request.body)
        assert parsed_body['api_key'] == 'REDACTED'

    @pytest.mark.parametrize('executor_class', [ThreadPoolExecutor, ProcessPoolExecutor])
    @pytest.mark.parametrize('iteration', range(N_ITERATIONS))
    def test_concurrency(self, iteration, executor_class):
        """Run multithreaded and multiprocess stress tests for each backend.
        The number of workers (thread/processes), iterations, and requests per iteration can be
        increased via the `STRESS_TEST_MULTIPLIER` environment variable.
        """
        start = time()
        url = httpbin('anything')

        # For multithreading, we can share a session object, but we can't for multiprocessing
        session = self.init_session(clear=True, expire_after=1)
        if executor_class is ProcessPoolExecutor:
            session = None
        session_factory = partial(self.init_session, clear=False, expire_after=1)

        request_func = partial(_send_request, session, session_factory, url)
        with executor_class(max_workers=N_WORKERS) as executor:
            _ = list(executor.map(request_func, range(N_REQUESTS_PER_ITERATION)))

        # Some logging for debug purposes
        elapsed = time() - start
        average = (elapsed * 1000) / (N_ITERATIONS * N_WORKERS)
        worker_type = 'threads' if executor_class is ThreadPoolExecutor else 'processes'
        logger.info(
            f'{self.backend_class.__name__}: Ran {N_REQUESTS_PER_ITERATION} requests with '
            f'{N_WORKERS} {worker_type} in {elapsed} s\n'
            f'Average time per request: {average} ms'
        )


def _send_request(session, session_factory, url, _=None):
    """Concurrent request function for stress tests. Defined in module scope so it can be serialized
    to multiple processes.
    """
    # Use fewer unique requests/cached responses than total iterations, so we get some cache hits
    n_unique_responses = int(N_REQUESTS_PER_ITERATION / 4)
    i = randint(1, n_unique_responses)

    # Threads can share a session object, but processes will create their own session because it
    # can't be serialized
    if session is None:
        session = session_factory()

    sleep(0.01)
    try:
        return session.get(url, params={f'key_{i}': f'value_{i}'})
    # Sometimes the local http server is the bottleneck here; just retry once
    except ConnectionError:
        sleep(0.1)
        return session.get(url, params={f'key_{i}': f'value_{i}'})
