#!/usr/bin/env python
"""
    requests_cache.backends.mongo
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    ``mongo`` cache backend
"""
from .base import BaseCache
from .storage.mongodict import MongoDict, MongoPickleDict


class MongoCache(BaseCache):
    """``mongo`` cache backend."""

    def __init__(self, db_name='requests-cache', **options):
        """
        :param db_name: database name (default: ``'requests-cache'``)
        :param connection: (optional) ``pymongo.Connection``
        """
        super().__init__(**options)
        self.responses = MongoPickleDict(db_name, 'responses', options.get('connection'))
        self.redirects = MongoDict(db_name, 'redirects', self.responses.connection)
