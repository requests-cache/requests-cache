#!/usr/bin/env python
import unittest

from tests.test_custom_dict import BaseCustomDictTestCase

try:
    from requests_cache.backends.redisdict import RedisDict
except ImportError:
    print("Redis not installed")
else:

    class RedisDictTestCase(BaseCustomDictTestCase, unittest.TestCase):
        dict_class = RedisDict
        pickled_dict_class = RedisDict

    if __name__ == '__main__':
        unittest.main()
