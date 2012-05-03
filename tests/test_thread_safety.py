#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Path hack
import os, sys
sys.path.insert(0, os.path.abspath('..'))

from threading import Thread
import unittest

import requests
import requests_cache

CACHE_BACKEND = 'sqlite'
CACHE_NAME = 'requests_cache_test'


class ThreadSafetyTestCase(unittest.TestCase):
    def test_caching_with_threads(self):
        requests_cache.configure(CACHE_NAME, CACHE_BACKEND)
        requests_cache.clear()
        n = 5
        url = 'http://httpbin.org/get'
        def do_requests(url, params):
            for i in range(10):
                requests.get(url, params=params)

        threads = [Thread(target=do_requests, args=(url, {'param': i})) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for i in range(n):
            self.assert_(requests_cache.has_url('%s?param=%s' % (url, i)))




if __name__ == '__main__':
    unittest.main()
