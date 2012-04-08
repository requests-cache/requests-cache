#!/usr/bin/env python
# -*- coding: utf-8 -*-
#date: 08.04.12
import unittest
import time

import requests

import requests_cache


class CacheTestCase(unittest.TestCase):

    def setUp(self):
        """setup"""
        requests_cache.configure()
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
        requests_cache.configure(expire_after=0.001)
        url = 'http://httpbin.org/response-headers?expire_test=1'
        r = requests.get(url)
        self.assertIn(url, requests_cache.get_cache().url_map)
        r = requests.get(url)
        self.assertNotIn(url, requests_cache.get_cache().url_map)

    def test_just_for_coverage(self):
        # str method and keys
        s = str(requests_cache.get_cache())
        url = 'http://httpbin.org/redirect/3'
        r = requests.get(url)
        # delete keys
        requests_cache.get_cache().del_cached_url(url)
        requests_cache.get_cache().del_cached_url('http://httpbin.org/redirect/3')
        url_map = requests_cache.get_cache().url_map
        with self.assertRaises(KeyError):
            del url_map['123']

        # update
        url_map['http://ya.ru/'] = 'htpp://??.ru'
        url_map['http://ya.ru/'] = 'htpp://ya.ru'

#        # del with history
#        requests.get('http://github.com/')
#        requests_cache.get_cache().del_cached_url('http://github.com/')

    def test_unregistered_backend(self):
        with self.assertRaises(ValueError):
            requests_cache.configure(backend='nonexistent')



if __name__ == '__main__':
    unittest.main()
