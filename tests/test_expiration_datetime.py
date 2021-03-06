#!/usr/bin/env python
import datetime
import itertools
import unittest

import requests

import requests_cache


class ExpirationTimeTest(unittest.TestCase):
    def setUp(self):
        requests_cache.install_cache(backend='memory')
        self.url = 'https://httpbin.org/get'
        self.session = requests.Session()
        self.now = datetime.datetime(2021, 2, 28, 16, 40)
        self.response = requests.Response()

    def tearDown(self):
        requests_cache.uninstall_cache()

    def test_expire_after_precedence_matrix(self):
        in_five_seconds = datetime.datetime(2021, 2, 28, 16, 40, 5)
        expire_afters = ['default', None, 5, datetime.timedelta(seconds=5), in_five_seconds]

        for cache_expire_after, request_expire_after, response_expire_after in itertools.product(
            expire_afters, expire_afters, expire_afters
        ):
            if cache_expire_after == 'default':
                continue  # cache can never be default or cached

            expected = False
            if request_expire_after == 'default':
                expected = in_five_seconds if cache_expire_after is not None else None
            else:
                expected = in_five_seconds if request_expire_after is not None else None

            self.session._cache_expire_after = cache_expire_after
            self.session._request_expire_after = request_expire_after
            self.response.expire_after = response_expire_after
            with self.subTest(cache=cache_expire_after, request=request_expire_after, response=response_expire_after):
                actual = self.session._determine_expiration_datetime(relative_to=self.now)
                self.assertEqual(actual, expected)
