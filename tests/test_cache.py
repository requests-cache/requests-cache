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
from requests import Request

import requests_cache
from requests_cache import CachedSession
from requests_cache.compat import bytes, str, is_py3

CACHE_BACKEND = 'sqlite'
CACHE_NAME = 'requests_cache_test'
FAST_SAVE = False

if 'HTTPBIN_URL' not in os.environ:
    os.environ['HTTPBIN_URL'] = 'http://httpbin.org/'

HTTPBIN_URL = os.environ.get('HTTPBIN_URL')


def httpbin(*suffix):
    """Returns url for HTTPBIN resource."""
    return HTTPBIN_URL + '/'.join(suffix)

class CacheTestCase(unittest.TestCase):

    def setUp(self):
        self.s = CachedSession(CACHE_NAME, backend=CACHE_BACKEND, fast_save=FAST_SAVE)
        self.s.cache.clear()
        requests_cache.uninstall_cache()

    def test_expire_cache(self):
        delay = 1
        url = httpbin('delay/%s' % delay)
        s = CachedSession(CACHE_NAME, backend=CACHE_BACKEND, expire_after=0.06)
        t = time.time()
        r = s.get(url)
        delta = time.time() - t
        self.assertGreaterEqual(delta, delay)
        time.sleep(0.5)
        t = time.time()
        r = s.get(url)
        delta = time.time() - t
        self.assertGreaterEqual(delta, delay)

    def test_delete_urls(self):
        url = httpbin('redirect/3')
        r = self.s.get(url)
        for i in range(1, 4):
            self.assert_(self.s.cache.has_url(httpbin('redirect/%s' % i)))
        self.s.cache.delete_url(url)
        self.assert_(not self.s.cache.has_url(url))

    def test_unregistered_backend(self):
        with self.assertRaises(ValueError):
            CachedSession(CACHE_NAME, backend='nonexistent')

#    def test_async_compatibility(self):
#        try:
#            import grequests
#        except Exception:
#            self.skipTest('gevent is not installed')
#        n = 3
#        def long_running():
#            t = time.time()
#            rs = [grequests.get(httpbin('delay/%s' % i)) for i in range(n + 1)]
#            grequests.map(rs)
#            return time.time() - t
#        # cache it
#        delta = long_running()
#        self.assertGreaterEqual(delta, n)
#        # fast from cache
#        delta = 0
#        for i in range(n):
#            delta += long_running()
#        self.assertLessEqual(delta, 1)

    def test_hooks(self):
        state = defaultdict(int)
        for hook in ('response',):  # TODO it's only one hook here

            def hook_func(r, *args, **kwargs):
                state[hook] += 1
                return r
            n = 5
            for i in range(n):
                r = self.s.get(httpbin('get'), hooks={hook: hook_func})
            self.assertEqual(state[hook], n)

    def test_attr_from_cache_in_hook(self):
        state = defaultdict(int)
        hook = 'response'

        def hook_func(r, *args, **kwargs):
            if state[hook] > 0:
                self.assert_(r.from_cache, True)
            state[hook] += 1
            return r
        n = 5
        for i in range(n):
            r = self.s.get(httpbin('get'), hooks={hook: hook_func})
        self.assertEqual(state[hook], n)

    def test_post(self):
        url = httpbin('post')
        r1 = json.loads(self.s.post(url, data={'test1': 'test1'}).text)
        r2 = json.loads(self.s.post(url, data={'test2': 'test2'}).text)
        self.assertIn('test2', r2['form'])
        req = Request('POST', url).prepare()
        self.assert_(not self.s.cache.has_key(self.s.cache.create_key(req)))

    def test_disabled(self):

        url = httpbin('get')
        requests_cache.install_cache(CACHE_NAME, backend=CACHE_BACKEND, fast_save=FAST_SAVE)
        requests.get(url)
        with requests_cache.disabled():
            for i in range(2):
                r = requests.get(url)
                self.assertFalse(getattr(r, 'from_cache', False))
        with self.s.cache_disabled():
            for i in range(2):
                r = self.s.get(url)
                self.assertFalse(getattr(r, 'from_cache', False))
        r = self.s.get(url)
        self.assertTrue(getattr(r, 'from_cache', False))

    def test_enabled(self):
        url = httpbin('get')
        options = dict(cache_name=CACHE_NAME, backend=CACHE_BACKEND,
                       fast_save=FAST_SAVE)
        with requests_cache.enabled(**options):
            r = requests.get(url)
            self.assertFalse(getattr(r, 'from_cache', False))
            for i in range(2):
                r = requests.get(url)
                self.assertTrue(getattr(r, 'from_cache', False))
        r = requests.get(url)
        self.assertFalse(getattr(r, 'from_cache', False))

    def test_content_and_cookies(self):
        requests_cache.install_cache(CACHE_NAME, CACHE_BACKEND)
        s = requests.session()
        def js(url):
            return json.loads(s.get(url).text)
        r1 = js(httpbin('cookies/set/test1/test2'))
        with requests_cache.disabled():
            r2 = js(httpbin('cookies'))
        self.assertEqual(r1, r2)
        r3 = js(httpbin('cookies'))
        with requests_cache.disabled():
            r4 = js(httpbin('cookies/set/test3/test4'))
        # from cache
        self.assertEqual(r3, js(httpbin('cookies')))
        # updated
        with requests_cache.disabled():
            self.assertEqual(r4, js(httpbin('cookies')))

    def test_response_history(self):
        r1 = self.s.get(httpbin('redirect/3'))
        def test_redirect_history(url):
            r2 = self.s.get(url)
            self.assertTrue(r2.from_cache)
            for r11, r22 in zip(r1.history, r2.history):
                self.assertEqual(r11.url, r22.url)
        test_redirect_history(httpbin('redirect/3'))
        test_redirect_history(httpbin('redirect/2'))
        r3 = requests.get(httpbin('redirect/1'))
        self.assertEqual(len(r3.history), 1)

    def test_response_history_simple(self):
        r1 = self.s.get(httpbin('redirect/2'))
        r2 = self.s.get(httpbin('redirect/1'))
        self.assertTrue(r2.from_cache)

    def post(self, data):
        return json.loads(self.s.post(httpbin('post'), data=data).text)

    def test_post_params(self):
        # issue #2
        self.s = CachedSession(CACHE_NAME, CACHE_BACKEND,
                               allowable_methods=('GET', 'POST'))

        d = {'param1': 'test1'}
        for _ in range(2):
            self.assertEqual(self.post(d)['form'], d)
            d = {'param1': 'test1', 'param3': 'test3'}
            self.assertEqual(self.post(d)['form'], d)

        self.assertTrue(self.s.post(httpbin('post'), data=d).from_cache)
        d.update({'something': 'else'})
        self.assertFalse(self.s.post(httpbin('post'), data=d).from_cache)

    def test_post_data(self):
        # issue #2, raw payload
        self.s = CachedSession(CACHE_NAME, CACHE_BACKEND,
                               allowable_methods=('GET', 'POST'))
        d1 = json.dumps({'param1': 'test1'})
        d2 = json.dumps({'param1': 'test1', 'param2': 'test2'})
        d3 = str('some unicode data')
        if is_py3:
            bin_data = bytes('some binary data', 'utf8')
        else:
            bin_data = bytes('some binary data')

        for d in (d1, d2, d3):
            self.assertEqual(self.post(d)['data'], d)
            r = self.s.post(httpbin('post'), data=d)
            self.assert_(hasattr(r, 'from_cache'))

        self.assertEqual(self.post(bin_data)['data'],
                         bin_data.decode('utf8'))
        r = self.s.post(httpbin('post'), data=bin_data)
        self.assert_(hasattr(r, 'from_cache'))

    def test_get_params_as_argument(self):
        for _ in range(5):
            p = {'arg1': 'value1'}
            r = self.s.get(httpbin('get'), params=p)
            self.assert_(self.s.cache.has_url( httpbin('get?arg1=value1')))

    def test_https_support(self):
        n = 10
        delay = 1
        url = 'https://httpbin.org/delay/%s?ar1=value1' % delay
        t = time.time()
        for _ in range(n):
            r = self.s.get(url, verify=False)
        self.assertLessEqual(time.time() - t, delay * n / 2)

    def test_from_cache_attribute(self):
        url = httpbin('get?q=1')
        self.assertFalse(self.s.get(url).from_cache)
        self.assertTrue(self.s.get(url).from_cache)
        self.s.cache.clear()
        self.assertFalse(self.s.get(url).from_cache)

    def test_gzip_response(self):
        url = httpbin('gzip')
        self.assertFalse(self.s.get(url).from_cache)
        self.assertTrue(self.s.get(url).from_cache)

    def test_close_response(self):
        for _ in range(3):
            r = self.s.get(httpbin("get"))
            r.close()


if __name__ == '__main__':
    unittest.main()
