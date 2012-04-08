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

    Reading is fast, saving is a bit slower. It can store big amount of data
    with low memory usage.

    It stores cache data to two files (for ``location = 'cache'``):

    - ``cache_urls.sqlite``
    - ``cache_responses.sqlite``
    """
    def __init__(self, location='cache', *args, **kwargs):
        """
        :param location: database filename prefix (default: ``'cache'``)
        """
        super(DbCache, self).__init__(*args, **kwargs)
        self.url_map = DbPickleDict('%s_urls' % location)
        self.responses = DbPickleDict('%s_responses' % location)
