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
from requests_cache.backends.storage.filesystemdict import FilesystemDict

class FilesystemDictTestCase(BaseCustomDictTestCase, unittest.TestCase):
    dict_class = FilesystemDict
    pickled_dict_class = FilesystemDict

if __name__ == '__main__':
    unittest.main()
