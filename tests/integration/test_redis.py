#!/usr/bin/env python
import unittest

from tests.integration.test_backends import BaseBackendTestCase

try:
    from requests_cache.backends.redis import RedisDict
except ImportError:
    print("Redis not installed")
else:

    class RedisTestCase(BaseBackendTestCase, unittest.TestCase):
        dict_class = RedisDict
        pickled_dict_class = RedisDict

    if __name__ == '__main__':
        unittest.main()
