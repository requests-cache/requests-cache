#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests

from requests_cache.backends.base import MemoryCache
from requests_cache.backends.dbdict import DbPickleDict


class DbCache(MemoryCache):
    """ sqlite cache backend
    """
    def __init__(self, location='cache', *args, **kwargs):
        super(DbCache, self).__init__(*args, **kwargs)
        self.url_map = DbPickleDict('%s_urls' % location)
        self.responses = DbPickleDict('%s_responses' % location)
