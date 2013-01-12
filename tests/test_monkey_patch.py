#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Path hack
import os, sys
sys.path.insert(0, os.path.abspath('..'))

import unittest

import requests

import requests_cache
from requests_cache import CachedSession

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


if __name__ == '__main__':
    unittest.main()
