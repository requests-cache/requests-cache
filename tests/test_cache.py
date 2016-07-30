#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Path hack
import os, sys
sys.path.insert(0, os.path.abspath('..'))

try:
    import unittest2 as unittest
except ImportError:
    import unittest

import time
import json
from collections import defaultdict
from datetime import datetime, timedelta

import mock
import requests
from requests import Request

import requests_cache
from requests_cache import CachedSession
from requests_cache.compat import bytes, str, is_py3

CACHE_BACKEND = 'sqlite'
CACHE_NAME = 'requests_cache_test'
FAST_SAVE = False

HTTPBIN_URL = os.getenv('HTTPBIN_URL', 'http://httpbin.org/')


def httpbin(*suffix):
    """Returns url for HTTPBIN resource."""
    return HTTPBIN_URL + '/'.join(suffix)


class CacheTestCase(unittest.TestCase):

    def setUp(self):
        self.s = CachedSession(CACHE_NAME, backend=CACHE_BACKEND, fast_save=FAST_SAVE)
        self.s.cache.clear()
        requests_cache.uninstall_cache()

    @classmethod
    def tearDownClass(cls):
        super(CacheTestCase, cls).tearDownClass()
        filename = "{0}.{1}".format(CACHE_NAME, CACHE_BACKEND)
        if os.path.exists(filename):
            try:
                os.unlink(filename)
            except OSError:
                pass

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
        url = httpbin('relative-redirect/3')
        r = self.s.get(url)
        for i in range(1, 4):
            self.assert_(self.s.cache.has_url(httpbin('relative-redirect/%s' % i)))
        self.s.cache.delete_url(url)
        self.assert_(not self.s.cache.has_url(url))

    def test_unregistered_backend(self):
        with self.assertRaises(ValueError):
            CachedSession(CACHE_NAME, backend='nonexistent')

    @mock.patch('requests_cache.backends.registry')
    def test_missing_backend_dependency(self, mocked_registry):
        # Testing that the correct error is thrown when a user does not have
        # the Python package `redis` installed.  We mock out the registry
        # to simulate `redis` not being installed.
        mocked_registry.__getitem__.side_effect = KeyError
        with self.assertRaises(ImportError):
            CachedSession(CACHE_NAME, backend='redis')

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
        r1 = self.s.get(httpbin('relative-redirect/3'))
        def test_redirect_history(url):
            r2 = self.s.get(url)
            self.assertTrue(r2.from_cache)
            for r11, r22 in zip(r1.history, r2.history):
                self.assertEqual(r11.url, r22.url)
        test_redirect_history(httpbin('relative-redirect/3'))
        test_redirect_history(httpbin('relative-redirect/2'))
        r3 = requests.get(httpbin('relative-redirect/1'))
        self.assertEqual(len(r3.history), 1)

    def test_response_history_simple(self):
        r1 = self.s.get(httpbin('relative-redirect/2'))
        r2 = self.s.get(httpbin('relative-redirect/1'))
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

    def test_get_parameters_normalization(self):
        url = httpbin("get")
        params = {"a": "a", "b": ["1", "2", "3"], "c": "4"}

        self.assertFalse(self.s.get(url, params=params).from_cache)
        r = self.s.get(url, params=params)
        self.assertTrue(r.from_cache)
        self.assertEquals(r.json()["args"], params)
        self.assertFalse(self.s.get(url, params={"a": "b"}).from_cache)
        self.assertTrue(self.s.get(url, params=sorted(params.items())).from_cache)

        class UserSubclass(dict):
            def items(self):
                return sorted(super(UserSubclass, self).items(), reverse=True)

        params["z"] = "5"
        custom_dict = UserSubclass(params)
        self.assertFalse(self.s.get(url, params=custom_dict).from_cache)
        self.assertTrue(self.s.get(url, params=custom_dict).from_cache)

    def test_post_parameters_normalization(self):
        params = {"a": "a", "b": ["1", "2", "3"], "c": "4"}
        url = httpbin("post")
        s = CachedSession(CACHE_NAME, CACHE_BACKEND,
                          allowable_methods=('GET', 'POST'))
        self.assertFalse(s.post(url, data=params).from_cache)
        self.assertTrue(s.post(url, data=params).from_cache)
        self.assertTrue(s.post(url, data=sorted(params.items())).from_cache)
        self.assertFalse(s.post(url, data=sorted(params.items(), reverse=True)).from_cache)

    def test_stream_requests_support(self):
        n = 100
        url = httpbin("stream/%s" % n)
        r = self.s.get(url, stream=True)
        first_char = r.raw.read(1)
        lines = list(r.iter_lines())
        self.assertTrue(first_char)
        self.assertEquals(len(lines), n)

        for i in range(2):
            r = self.s.get(url, stream=True)
            first_char_cached = r.raw.read(1)
            self.assertTrue(r.from_cache)
            cached_lines = list(r.iter_lines())
            self.assertEquals(cached_lines, lines)
            self.assertEquals(first_char, first_char_cached)

    def test_headers_in_get_query(self):
        url = httpbin("get")
        s = CachedSession(CACHE_NAME, CACHE_BACKEND, include_get_headers=True)
        headers = {"Accept": "text/json"}
        self.assertFalse(s.get(url, headers=headers).from_cache)
        self.assertTrue(s.get(url, headers=headers).from_cache)

        headers["Accept"] = "text/xml"
        self.assertFalse(s.get(url, headers=headers).from_cache)
        self.assertTrue(s.get(url, headers=headers).from_cache)

        headers["X-custom-header"] = "custom"
        self.assertFalse(s.get(url, headers=headers).from_cache)
        self.assertTrue(s.get(url, headers=headers).from_cache)

        self.assertFalse(s.get(url).from_cache)
        self.assertTrue(s.get(url).from_cache)

    def test_str_and_repr(self):
        s = repr(CachedSession(CACHE_NAME, CACHE_BACKEND, expire_after=10))
        self.assertIn(CACHE_NAME, s)
        self.assertIn("10", s)

    @mock.patch("requests_cache.core.datetime")
    def test_return_old_data_on_error(self, datetime_mock):
        datetime_mock.utcnow.return_value = datetime.utcnow()
        expire_after = 100
        url = httpbin("get")
        s = CachedSession(CACHE_NAME, CACHE_BACKEND, old_data_on_error=True, expire_after=expire_after)
        header = "X-Tst"

        def get(n):
            return s.get(url, headers={header: n}).json()["headers"][header]

        get("expired")
        self.assertEquals(get("2"), "expired")
        datetime_mock.utcnow.return_value = datetime.utcnow() + timedelta(seconds=expire_after * 2)

        with mock.patch.object(s.cache, "save_response", side_effect=Exception):
            self.assertEquals(get("3"), "expired")

        with mock.patch("requests_cache.core.OriginalSession.send") as send_mock:
            resp_mock = requests.Response()
            request = requests.Request("GET", url)
            resp_mock.request = request.prepare()
            resp_mock.status_code = 400
            resp_mock._content = '{"other": "content"}'
            send_mock.return_value = resp_mock
            self.assertEquals(get("3"), "expired")

            resp_mock.status_code = 200
            self.assertIs(s.get(url).content, resp_mock.content)

        # default behaviour
        datetime_mock.return_value = datetime.utcnow() + timedelta(seconds=expire_after * 2)
        s = CachedSession(CACHE_NAME, CACHE_BACKEND, old_data_on_error=False, expire_after=100)
        with mock.patch.object(s.cache, "save_response", side_effect=Exception):
            with self.assertRaises(Exception):
                s.get(url)

    def test_ignore_parameters_get(self):
        url = httpbin("get")
        ignored_param = "ignored"
        usual_param = "some"
        params = {ignored_param: "1", usual_param: "1"}

        s = CachedSession(CACHE_NAME, CACHE_BACKEND,
                          ignored_parameters=[ignored_param])

        r = s.get(url, params=params)
        self.assertIn(ignored_param, r.json()['args'].keys())
        self.assertFalse(r.from_cache)

        self.assertTrue(s.get(url, params=params).from_cache)

        params[ignored_param] = "new"
        self.assertTrue(s.get(url, params=params).from_cache)

        params[usual_param] = "new"
        self.assertFalse(s.get(url, params=params).from_cache)

    def test_ignore_parameters_post(self):
        url = httpbin("post")
        ignored_param = "ignored"
        usual_param = "some"
        d = {ignored_param: "1", usual_param: "1"}

        s = CachedSession(CACHE_NAME, CACHE_BACKEND,
                          allowable_methods=('POST'),
                          ignored_parameters=[ignored_param])

        r = s.post(url, data=d)
        self.assertIn(ignored_param, r.json()['form'].keys())
        self.assertFalse(r.from_cache)

        self.assertTrue(s.post(url, data=d).from_cache)

        d[ignored_param] = "new"
        self.assertTrue(s.post(url, data=d).from_cache)

        d[usual_param] = "new"
        self.assertFalse(s.post(url, data=d).from_cache)

    def test_ignore_parameters_post_json(self):
        url = httpbin("post")
        ignored_param = "ignored"
        usual_param = "some"
        d = {ignored_param: "1", usual_param: "1"}

        s = CachedSession(CACHE_NAME, CACHE_BACKEND,
                          allowable_methods=('POST'),
                          ignored_parameters=[ignored_param])

        r = s.post(url, json=d)
        self.assertIn(ignored_param, json.loads(r.json()['data']).keys())
        self.assertFalse(r.from_cache)

        self.assertTrue(s.post(url, json=d).from_cache)

        d[ignored_param] = "new"
        self.assertTrue(s.post(url, json=d).from_cache)

        d[usual_param] = "new"
        self.assertFalse(s.post(url, json=d).from_cache)

    def test_ignore_parameters_post_raw(self):
        url = httpbin("post")
        ignored_param = "ignored"
        raw_data = "raw test data"

        s = CachedSession(CACHE_NAME, CACHE_BACKEND,
                          allowable_methods=('POST'),
                          ignored_parameters=[ignored_param])

        self.assertFalse(s.post(url, data=raw_data).from_cache)
        self.assertTrue(s.post(url, data=raw_data).from_cache)

        raw_data = "new raw data"
        self.assertFalse(s.post(url, data=raw_data).from_cache)

    @mock.patch("requests_cache.backends.base.datetime")
    @mock.patch("requests_cache.core.datetime")
    def test_remove_expired_entries(self, datetime_mock, datetime_mock2):
        expire_after = timedelta(minutes=10)
        start_time = datetime.utcnow().replace(year=2010, minute=0)
        datetime_mock.utcnow.return_value = start_time
        datetime_mock2.utcnow.return_value = start_time

        s = CachedSession(CACHE_NAME, CACHE_BACKEND, expire_after=expire_after)
        s.get(httpbin('get'))
        s.get(httpbin('relative-redirect/3'))
        datetime_mock.utcnow.return_value = start_time + expire_after * 2
        datetime_mock2.utcnow.return_value = datetime_mock.utcnow.return_value

        ok_url = 'get?x=1'
        s.get(httpbin(ok_url))
        self.assertEqual(len(s.cache.responses), 3)
        self.assertEqual(len(s.cache.keys_map), 3)
        s.remove_expired_responses()
        self.assertEqual(len(s.cache.responses), 1)
        self.assertEqual(len(s.cache.keys_map), 0)
        self.assertIn(ok_url, list(s.cache.responses.values())[0][0].url)


if __name__ == '__main__':
    unittest.main()
