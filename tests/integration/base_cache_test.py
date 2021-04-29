"""Common tests to run for all backends (BaseCache subclasses)"""
import json
import pytest
from threading import Thread
from time import sleep, time
from typing import Dict, Type

from requests_cache import ALL_METHODS, CachedResponse, CachedSession
from requests_cache.backends.base import BaseCache
from tests.conftest import (
    CACHE_NAME,
    HTTPBIN_FORMATS,
    HTTPBIN_METHODS,
    N_ITERATIONS,
    N_THREADS,
    USE_PYTEST_HTTPBIN,
    httpbin,
)


class BaseCacheTest:
    """Base class for testing cache backend classes"""

    backend_class: Type[BaseCache] = None
    init_kwargs: Dict = {}

    def init_session(self, clear=True, **kwargs) -> CachedSession:
        kwargs.update({'allowable_methods': ALL_METHODS, 'suppress_warnings': True})
        backend = self.backend_class(CACHE_NAME, **self.init_kwargs, **kwargs)
        if clear:
            backend.redirects.clear()
            backend.responses.clear()

        return CachedSession(backend=backend, **self.init_kwargs, **kwargs)

    @pytest.mark.parametrize('method', HTTPBIN_METHODS)
    @pytest.mark.parametrize('field', ['params', 'data', 'json'])
    def test_all_methods(self, field, method):
        """Test all relevant combinations of methods and data fields. Requests with different request
        params, data, or json should be cached under different keys.
        """
        url = httpbin(method.lower())
        session = self.init_session()
        for params in [{'param_1': 1}, {'param_1': 2}, {'param_2': 2}]:
            assert session.request(method, url, **{field: params}).from_cache is False
            assert session.request(method, url, **{field: params}).from_cache is True

    @pytest.mark.parametrize('response_format', HTTPBIN_FORMATS)
    def test_all_response_formats(self, response_format):
        """Test that all relevant response formats are cached correctly"""
        session = self.init_session()
        # Temporary workaround for this issue: https://github.com/kevin1024/pytest-httpbin/issues/60
        if response_format == 'json' and USE_PYTEST_HTTPBIN:
            session.allowable_codes = (200, 404)

        r1 = session.get(httpbin(response_format))
        r2 = session.get(httpbin(response_format))
        assert r1.from_cache is False
        assert r2.from_cache is True
        assert r1.content == r2.content

    @pytest.mark.parametrize('n_redirects', range(1, 5))
    @pytest.mark.parametrize('endpoint', ['redirect', 'absolute-redirect', 'relative-redirect'])
    def test_redirects(self, endpoint, n_redirects):
        """Test all types of redirect endpoints with different numbers of consecutive redirects"""
        session = self.init_session()
        session.get(httpbin(f'{endpoint}/{n_redirects}'))
        r2 = session.get(httpbin('get'))

        assert r2.from_cache is True
        assert len(session.cache.redirects) == n_redirects

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

    def test_response_decode(self):
        """Test that a gzip-compressed raw response can be manually uncompressed with decode_content"""
        session = self.init_session()
        response = session.get(httpbin('gzip'))
        assert b'gzipped' in response.content

        cached = CachedResponse(response)
        assert b'gzipped' in cached.content
        assert b'gzipped' in cached.raw.read(None, decode_content=True)

    def test_response_decode_stream(self):
        """Test that streamed gzip-compressed responses can be uncompressed with decode_content"""
        session = self.init_session()
        response_uncached = session.get(httpbin('gzip'), stream=True)
        response_cached = session.get(httpbin('gzip'), stream=True)

        for res in (response_uncached, response_cached):
            assert b'gzipped' in res.content
            assert b'gzipped' in res.raw.read(None, decode_content=True)

    def test_remove_expired_responses(self):
        session = self.init_session(expire_after=0.01)

        # Populate the cache with several responses that should expire immediately
        for response_format in HTTPBIN_FORMATS:
            session.get(httpbin(response_format))
        session.get(httpbin('redirect/1'))
        sleep(0.01)

        # Cache a response + redirects, which should be the only non-expired cache items
        session.get(httpbin('get'), expire_after=-1)
        session.get(httpbin('redirect/3'), expire_after=-1)
        session.cache.remove_expired_responses()

        assert len(session.cache.responses.keys()) == 2
        assert len(session.cache.redirects.keys()) == 3
        assert not session.cache.has_url(httpbin('redirect/1'))
        assert not any([session.cache.has_url(httpbin(f)) for f in HTTPBIN_FORMATS])

    @pytest.mark.parametrize('iteration', range(N_ITERATIONS))
    def test_multithreaded(self, iteration):
        """Run a multi-threaded stress test for each backend"""
        session = self.init_session()
        start = time()
        url = httpbin('anything')

        def send_requests():
            for i in range(N_ITERATIONS):
                session.get(url, params={f'key_{i}': f'value_{i}'})

        threads = [Thread(target=send_requests) for i in range(N_THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        elapsed = time() - start
        average = (elapsed * 1000) / (N_ITERATIONS * N_THREADS)
        print(f'{self.backend_class}: Ran {N_ITERATIONS} iterations with {N_THREADS} threads each in {elapsed} s')
        print(f'Average time per request: {average} ms')

        for i in range(N_ITERATIONS):
            assert session.cache.has_url(f'{url}?key_{i}=value_{i}')
