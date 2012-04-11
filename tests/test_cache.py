#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Path hack
import os, sys
sys.path.insert(0, os.path.abspath('..'))

import unittest
import time
import json
from collections import defaultdict

import requests

import requests_cache

CACHE_BACKEND = 'sqlite'
CACHE_NAME = 'requests_cache_test'


class CacheTestCase(unittest.TestCase):

    def setUp(self):
        requests_cache.configure(CACHE_NAME, backend=CACHE_BACKEND)
        requests_cache.clear()

    def test_speedup_and_undo_redo_patch(self):
        delay = 1
        def long_request():
            t = time.time()
            for i in range(5):
                r = requests.get('http://httpbin.org/delay/%s' % delay)
            delta = time.time() - t
            self.assertLess(delta, delay * 3)
        long_request()
        requests_cache.undo_patch()
        t = time.time()
        r = requests.get('http://httpbin.org/delay/%s' % delay)
        delta = time.time() - t
        self.assertGreaterEqual(delta, delay)
        requests_cache.redo_patch()
        long_request()

    def test_expire_cache(self):
        delay = 1
        url = 'http://httpbin.org/delay/%s' % delay
        requests_cache.configure(CACHE_NAME, backend=CACHE_BACKEND, expire_after=0.001)
        t = time.time()
        r = requests.get(url)
        delta = time.time() - t
        self.assertGreaterEqual(delta, delay)
        time.sleep(0.5)
        t = time.time()
        r = requests.get(url)
        delta = time.time() - t
        self.assertGreaterEqual(delta, delay)

    def test_delete_urls(self):
        url = 'http://httpbin.org/redirect/3'
        r = requests.get(url)
        for i in range(1, 4):
            self.assert_(requests_cache.has_url('http://httpbin.org/redirect/%s' % i))
        requests_cache.delete_url(url)
        self.assert_(not requests_cache.has_url(url))

    def test_unregistered_backend(self):
        with self.assertRaises(ValueError):
            requests_cache.configure(CACHE_NAME, backend='nonexistent')

    def test_async_compatibility(self):
        try:
            from requests import async
        except Exception:
            self.fail('gevent is not installed')
        n = 3
        def long_running():
            t = time.time()
            rs = [async.get('http://httpbin.org/delay/%s' % i) for i in range(n + 1)]
            async.map(rs)
            return time.time() - t
        # cache it
        delta = long_running()
        self.assertGreaterEqual(delta, n)
        # fast from cache
        delta = 0
        for i in range(n):
            delta += long_running()
        self.assertLessEqual(delta, 1)

    def test_hooks(self):
        state = defaultdict(int)
        for hook in ('response', 'post_request'):

            def hook_func(r):
                state[hook] += 1
                return r
            n = 5
            for i in range(n):
                r = requests.get('http://httpbin.org/get', hooks={hook: hook_func})
            self.assertEqual(state[hook], n)

    def test_post(self):
        url = 'http://httpbin.org/post'
        r1 = json.loads(requests.post(url, data={'test1': 'test1'}).text)
        r2 = json.loads(requests.post(url, data={'test2': 'test2'}).text)
        self.assertIn('test2', r2['form'])
        self.assert_(not requests_cache.has_url(url))

    def test_disabled_enabled(self):
        delay = 1
        url = 'http://httpbin.org/delay/%s' % delay
        with requests_cache.disabled():
            t = time.time()
            n = 2
            for i in range(n):
                requests.get(url)
            delta = time.time() - t
            self.assertGreaterEqual(delta, delay * n)

        with requests_cache.enabled():
            t = time.time()
            n = 5
            for i in range(n):
                requests.get(url)
            delta = time.time() - t
            self.assertLessEqual(delta, delay * n)

    def test_content_and_cookies(self):
        s = requests.session()
        def js(url):
            return json.loads(s.get(url).text)
        r1 = js('http://httpbin.org/cookies/set/test1/test2')
        with requests_cache.disabled():
            r2 = js('http://httpbin.org/cookies')
        self.assertEqual(r1, r2)
        r3 = js('http://httpbin.org/cookies')
        with requests_cache.disabled():
            r4 = js('http://httpbin.org/cookies/set/test3/test4')
        # from cache
        self.assertEqual(r3, js('http://httpbin.org/cookies'))
        # updated
        with requests_cache.disabled():
            self.assertEqual(r4, js('http://httpbin.org/cookies'))

    def test_response_history(self):
        r1 = requests.get('http://httpbin.org/redirect/3')
        def test_redirect_history(url):
            r2 = requests.get(url)
            for r11, r22 in zip(r1.history, r2.history):
                self.assertEqual(r11.url, r22.url)
        test_redirect_history('http://httpbin.org/redirect/3')
        test_redirect_history('http://httpbin.org/redirect/2')
        with requests_cache.disabled():
            r3 = requests.get('http://httpbin.org/redirect/1')
            self.assertEqual(len(r3.history), 1)


    # TODO: https test

if __name__ == '__main__':
    unittest.main()
