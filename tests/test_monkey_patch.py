#!/usr/bin/env python
import unittest
from unittest.mock import patch

import requests
from requests.sessions import Session as OriginalSession

import requests_cache
from requests_cache import CachedSession
from requests_cache.backends import BaseCache

CACHE_NAME = 'requests_cache_test'
CACHE_BACKEND = 'sqlite'
FAST_SAVE = False


class MonkeyPatchTestCase(unittest.TestCase):
    def setUp(self):
        requests_cache.install_cache(name=CACHE_NAME, backend=CACHE_BACKEND)
        requests.Session().cache.clear()
        requests_cache.uninstall_cache()

    def test_install_uninstall(self):
        for _ in range(2):
            requests_cache.install_cache(name=CACHE_NAME, backend=CACHE_BACKEND)
            self.assertTrue(isinstance(requests.Session(), CachedSession))
            self.assertTrue(isinstance(requests.sessions.Session(), CachedSession))
            self.assertTrue(isinstance(requests.session(), CachedSession))
            requests_cache.uninstall_cache()
            self.assertFalse(isinstance(requests.Session(), CachedSession))
            self.assertFalse(isinstance(requests.sessions.Session(), CachedSession))
            self.assertFalse(isinstance(requests.session(), CachedSession))

    def test_requests_from_cache(self):
        requests_cache.install_cache(name=CACHE_NAME, backend=CACHE_BACKEND)
        r = requests.get('http://httpbin.org/get')
        self.assertFalse(r.from_cache)
        r = requests.get('http://httpbin.org/get')
        self.assertTrue(r.from_cache)

    def test_session_is_a_class_with_original_attributes(self):
        requests_cache.install_cache(name=CACHE_NAME, backend=CACHE_BACKEND)
        self.assertTrue(isinstance(requests.Session, type))
        for attribute in dir(OriginalSession):
            self.assertTrue(hasattr(requests.Session, attribute))
        self.assertTrue(isinstance(requests.Session(), CachedSession))

    def test_inheritance_after_monkey_patch(self):
        requests_cache.install_cache(name=CACHE_NAME, backend=CACHE_BACKEND)

        class FooSession(requests.Session):
            __attrs__ = requests.Session.__attrs__ + ["new_one"]

            def __init__(self, param):
                self.param = param
                super(FooSession, self).__init__()

        s = FooSession(1)
        self.assertEqual(s.param, 1)
        self.assertIn("new_one", s.__attrs__)
        self.assertTrue(isinstance(s, CachedSession))

    def test_passing_backend_instance_support(self):
        class MyCache(BaseCache):
            pass

        backend = MyCache()
        requests_cache.install_cache(name=CACHE_NAME, backend=backend)
        self.assertIs(requests.Session().cache, backend)

        session = CachedSession(backend=backend)
        self.assertIs(session.cache, backend)

    @patch.object(BaseCache, 'remove_old_entries')
    def test_remove_expired_responses(self, remove_old_entries):
        requests_cache.install_cache(expire_after=360)
        requests_cache.remove_expired_responses()
        assert remove_old_entries.called is True

    @patch.object(BaseCache, 'remove_old_entries')
    def test_remove_expired_responses__cache_not_installed(self, remove_old_entries):
        requests_cache.remove_expired_responses()
        assert remove_old_entries.called is False

    @patch.object(BaseCache, 'remove_old_entries')
    def test_remove_expired_responses__no_expiration(self, remove_old_entries):
        requests_cache.install_cache()
        requests_cache.remove_expired_responses()
        # Before https://github.com/reclosedev/requests-cache/pull/177, this
        # was False, but with per-request caching, remove_old_entries must
        # always be called
        assert remove_old_entries.called is True


if __name__ == '__main__':
    unittest.main()
