#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Path hack
import os, sys
sys.path.insert(0, os.path.abspath('..'))

import unittest
import time
import json
from collections import defaultdict

from requests import Session
import requests
from requests import Request

import requests_cache
from requests_cache import CachedSession
from requests_cache.compat import bytes, str, is_py3

CACHE_NAME = 'requests_cache_test'
CACHE_BACKEND = 'sqlite'
FAST_SAVE = False


class MonkeyPatchTestCase(unittest.TestCase):

    def test_install_uninstall(self):
        for _ in range(2):
            requests_cache.install_cache(name=CACHE_NAME, backend=CACHE_BACKEND)
            self.assert_(isinstance(requests.Session(), CachedSession))
            self.assert_(isinstance(requests.sessions.Session(), CachedSession))
            self.assert_(isinstance(requests.session(), CachedSession))
            requests_cache.uninstall_cache()
            self.assert_(not isinstance(requests.Session(), CachedSession))
            self.assert_(not isinstance(requests.sessions.Session(), CachedSession))
            self.assert_(not isinstance(requests.session(), CachedSession))



if __name__ == '__main__':
    unittest.main()
