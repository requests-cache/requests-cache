#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    requests_cache.backends.sqlite
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    ``sqlite3`` cache backend
"""
from requests_cache.backends.base import BaseCache
from requests_cache.backends.dbdict import DbDict, DbPickleDict


class DbCache(BaseCache):
    """ sqlite cache backend.

    Reading is fast, saving is a bit slower. It can store big amount of data
    with low memory usage.
    """
    def __init__(self, location='cache', **options):
        """
        :param location: database filename prefix (default: ``'cache'``)
        """
        super(DbCache, self).__init__()
        self.responses = DbPickleDict(location, 'responses')
        self.url_map = DbDict(location, 'urls', self.responses)

