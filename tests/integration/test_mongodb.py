#!/usr/bin/env python
import unittest

from tests.integration.test_backends import BaseBackendTestCase

try:
    from requests_cache.backends.mongo import MongoDict, MongoPickleDict
except ImportError:
    print("pymongo not installed")
else:

    class MongoDBTestCase(BaseBackendTestCase, unittest.TestCase):
        dict_class = MongoDict
        pickled_dict_class = MongoPickleDict

    if __name__ == '__main__':
        unittest.main()
