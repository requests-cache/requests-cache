#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Path hack
import os, sys
import mock
sys.path.insert(0, os.path.abspath('..'))

try:
    import unittest2 as unittest
except ImportError:
    import unittest

from tests.test_custom_dict import BaseCustomDictTestCase
try:
    from requests_cache.backends.storage.mongodict import MongoDict, MongoPickleDict, is_pymongo_v3
    import pymongo
except ImportError:
    print("pymongo not installed")
else:
    class MongoDictTestCase(BaseCustomDictTestCase, unittest.TestCase):
        dict_class = MongoDict
        pickled_dict_class = MongoPickleDict

        @mock.patch('requests_cache.backends.storage.mongodict.pymongo', spec=pymongo)
        def test_is_pymongo_v3_should_return_True(self, _pymongo):
            _pymongo.version = '3.2.0'
            self.assertTrue(is_pymongo_v3())

        @mock.patch('requests_cache.backends.storage.mongodict.pymongo', spec=pymongo)
        def test_is_pymongo_v3_should_return_False(self, _pymongo):
            _pymongo.version = '2.9.0'
            self.assertFalse(is_pymongo_v3())

    if __name__ == '__main__':
        unittest.main()
