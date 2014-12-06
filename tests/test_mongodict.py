#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Path hack
import os, sys
sys.path.insert(0, os.path.abspath('..'))

try:
    import unittest2 as unittest
except ImportError:
    import unittest

from tests.test_custom_dict import BaseCustomDictTestCase
try:
    from requests_cache.backends.storage.mongodict import MongoDict, MongoPickleDict
except ImportError:
    print("pymongo not installed")
else:
    class MongoDictTestCase(BaseCustomDictTestCase, unittest.TestCase):
        dict_class = MongoDict
        pickled_dict_class = MongoPickleDict


    if __name__ == '__main__':
        unittest.main()
