#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Path hack
import os, sys
sys.path.insert(0, os.path.abspath('..'))

from threading import Thread
import unittest

import requests
import requests_cache

CACHE_NAME = 'requests_cache_test'


class ThreadSafetyTestCase(unittest.TestCase):

    def test_caching_with_threads(self):

        def do_tests_for(backend):
            requests_cache.configure(CACHE_NAME, backend)
            requests_cache.clear()
            n_threads = 10
            url = 'http://httpbin.org/get'
            def do_requests(url, params):
                for i in range(10):  # for testing write and read from cache
                    requests.get(url, params=params)

            for _ in range(20): # stress test
                threads = [Thread(target=do_requests, args=(url, {'param': i})) for i in range(n_threads)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

                for i in range(n_threads):
                    self.assert_(requests_cache.has_url('%s?param=%s' % (url, i)))

        for backend in ('sqlite', 'mongodb'):
            try:
                do_tests_for(backend)
            except Exception:
                print("Failed to test %s" % backend)


if __name__ == '__main__':
    unittest.main()
