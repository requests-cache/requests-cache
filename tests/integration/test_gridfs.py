#!/usr/bin/env python
import unittest

from tests.integration.test_backends import BaseBackendTestCase

try:
    from requests_cache.backends.gridfs import GridFSPickleDict
    from requests_cache.backends.mongo import MongoDict

except ImportError:
    print("pymongo not installed")
else:

    class GridFSTestCase(BaseBackendTestCase, unittest.TestCase):
        dict_class = MongoDict
        pickled_dict_class = GridFSPickleDict

    if __name__ == '__main__':
        unittest.main()
