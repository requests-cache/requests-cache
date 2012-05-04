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
    def __init__(self, location='cache', fast_save=False, **options):
        """
        :param location: database filename prefix (default: ``'cache'``)
        :param fast_save: Speedup cache saving up to 50 times but with possibility of data loss.
                          See :ref:`backends.DbDict <backends_dbdict>` for more info
        """
        super(DbCache, self).__init__()
        self.responses = DbPickleDict(location, 'responses', fast_save=fast_save)
        self.url_map = DbDict(location, 'urls')

