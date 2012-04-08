#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    requests_cache.backends.sqlite
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    ``sqlite3`` cache backend
"""
from requests_cache.backends.base import MemoryCache
from requests_cache.backends.dbdict import DbPickleDict


class DbCache(MemoryCache):
    """ sqlite cache backend.

    It stores cache data to two files (for ``location = 'cache'``):

    - ``cache_urls.sqlite``
    - ``cache_responses.sqlite``

    Reading is fast, saving is bit slower. It can store big amount of data
    with low memory usage.
    """
    def __init__(self, location='cache', *args, **kwargs):
        super(DbCache, self).__init__(*args, **kwargs)
        self.url_map = DbPickleDict('%s_urls' % location)
        self.responses = DbPickleDict('%s_responses' % location)
