#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    requests_cache.backends.mongo
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    ``mongo`` cache backend
"""
from requests_cache.backends.base import MemoryCache
from requests_cache.backends.mongodict import MongoDict, MongoPickleDict

# TODO: reusable connection
class MongoCache(MemoryCache):
    """ ``mongo`` cache backend.
    """
    def __init__(self, db_name='requests-cache'):
        """
        :param db_name: database name (default: ``'requests-cache'``)
        """
        super(MongoCache, self).__init__()
        self.responses = MongoPickleDict(db_name, 'responses')
        self.url_map = MongoDict(db_name, 'urls', self.responses.connection)

