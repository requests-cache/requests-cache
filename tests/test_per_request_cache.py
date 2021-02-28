#!/usr/bin/env python
import time
import unittest

import requests

import requests_cache
from requests_cache import PerRequestCachedSession
from requests_cache.per_request import RequestRegistry


class PerRequestCachedSessionTest(unittest.TestCase):
    def setUp(self):
        requests_cache.install_cache(backend='memory', session_factory=PerRequestCachedSession)
        PerRequestCachedSession.registry = RequestRegistry()
        self.url = 'https://httpbin.org/get'

    def tearDown(self):
        requests_cache.uninstall_cache()

    def test_default_cache_always(self):
        response = requests.get(self.url)
        assert not response.from_cache

        response = requests.get(self.url)
        assert response.from_cache

        response = requests.get(self.url, expire_after='default')
        assert response.from_cache

    def test_default_cache_never(self):
        requests_cache.install_cache(backend='memory', session_factory=PerRequestCachedSession, expire_after=-1)

        response = requests.get(self.url)
        assert not response.from_cache

        response = requests.get(self.url)
        assert not response.from_cache

        response = requests.get(self.url, expire_after='default')
        assert not response.from_cache

    def test_positive_cache(self):
        response = requests.get(self.url, expire_after=0.1)
        assert not response.from_cache

        time.sleep(0.5)

        response = requests.get(self.url)
        assert not response.from_cache

        # This should delete the cached entry before as it changed
        response = requests.get(self.url, expire_after=5)
        assert not response.from_cache

        # This should not delete the cached entry before as it didn't change
        response = requests.get(self.url, expire_after=5)
        assert response.from_cache

    def test_negative_cache(self):
        response = requests.get(self.url)
        assert not response.from_cache

        response = requests.get(self.url)
        assert response.from_cache

        response = requests.get(self.url, expire_after=-1)
        assert not response.from_cache

        response = requests.get(self.url, expire_after=-1)
        assert not response.from_cache

    def test_cache_invalidation(self):
        assert not requests.get(self.url, expire_after=1).from_cache
        assert requests.get(self.url).from_cache
        time.sleep(1.2)
        assert not requests.get(self.url).from_cache

        assert not requests.get(self.url, expire_after=-1).from_cache
        assert not requests.get(self.url).from_cache

        assert not requests.get(self.url, expire_after=1).from_cache
        assert requests.get(self.url).from_cache

    def test_auto_clear_expired(self):
        requests_cache.install_cache(backend='memory', session_factory=PerRequestCachedSession, expire_after=1)

        second_url = 'https://httpbin.org/anything'

        response = requests.get(self.url, expire_after=5)
        assert not response.from_cache

        response = requests.get(self.url)
        assert response.from_cache

        response = requests.get(second_url)
        assert not response.from_cache

        time.sleep(2)

        response = requests.get(self.url)
        assert response.from_cache

        response = requests.get(second_url, expire_after=10)
        assert not response.from_cache

        response = requests.get(second_url)
        assert response.from_cache

    def test_remove_expired(self):
        response = requests.get(self.url)
        assert not response.from_cache

        response = requests.get(self.url)
        assert response.from_cache

        second_url = 'https://httpbin.org/anything'

        response = requests.get(second_url, expire_after=2)
        assert not response.from_cache

        response = requests.get(second_url)
        assert response.from_cache

        third_url = 'https://httpbin.org/'

        response = requests.get(third_url, expire_after=10)
        assert not response.from_cache

        response = requests.get(third_url)
        assert response.from_cache

        assert len(requests.Session().cache.responses) == 3

        time.sleep(2)

        # TODO: This should be without `core`. Investigate!
        # requests_cache.remove_expired_responses()
        requests_cache.core.remove_expired_responses()

        assert len(requests.Session().cache.responses) == 2

    def test_remove_expired_expire_by_default(self):
        requests_cache.install_cache(backend='memory', session_factory=PerRequestCachedSession, expire_after=1)

        response = requests.get(self.url)
        assert not response.from_cache

        response = requests.get(self.url)
        assert response.from_cache

        second_url = 'https://httpbin.org/anything'

        response = requests.get(second_url, expire_after=10)
        assert not response.from_cache

        response = requests.get(second_url)
        assert response.from_cache

        assert len(requests.Session().cache.responses) == 2

        time.sleep(1)

        requests_cache.core.remove_expired_responses()

        assert len(requests.Session().cache.responses) == 1


class ContextManagerTest(unittest.TestCase):
    def test_as_context_manager(self):
        url = 'https://httpbin.org/delay/2'
        with requests_cache.enabled(session_factory=PerRequestCachedSession, expire_after=10):
            response = requests.get(url)
            assert not response.from_cache

            response = requests.get(url)
            assert response.from_cache

        start = time.time()
        response = requests.get(url)
        end = time.time()
        assert not hasattr(response, 'from_cache')
        assert end - start >= 1.5

        with requests_cache.enabled(session_factory=PerRequestCachedSession):
            response = requests.get(url)
            assert response.from_cache


if __name__ == '__main__':
    unittest.main()
