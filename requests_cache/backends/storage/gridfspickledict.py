#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    requests_cache.backends.mongodict
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Dictionary-like objects for saving large data sets to ``mongodb`` database
"""

try:
    from collections.abc import MutableMapping
except ImportError:
    from collections import MutableMapping
try:
    import cPickle as pickle
except ImportError:
    import pickle

# Use PyMongo 3 if present
try:
    from pymongo import MongoClient
except ImportError:
    from pymongo import Connection as MongoClient

from gridfs import GridFS

class GridFSPickleDict(MutableMapping):
    """ MongoDict - a dictionary-like interface for ``mongo`` database
    """
    def __init__(self, db_name, connection=None):
        """
        :param db_name: database name (be careful with production databases)
        :param connection: ``pymongo.Connection`` instance. If it's ``None``
                           (default) new connection with default options will
                           be created
        """
        if connection is not None:
            self.connection = connection
        else:
            self.connection = MongoClient()

        self.db = self.connection[db_name]
        self.fs = GridFS(self.db)

    def __getitem__(self, key):
        result = self.fs.find_one({'_id': key})
        if result is None:
            raise KeyError
        return pickle.loads(bytes(result.read()))

    def __setitem__(self, key, item):
        self.__delitem__(key)
        self.fs.put(pickle.dumps(item), **{'_id': key})

    def __delitem__(self, key):
        res = self.fs.find_one({'_id': key})
        if res is not None:
            self.fs.delete(res._id)

    def __len__(self):
        return self.db['fs.files'].count()

    def __iter__(self):
        for d in self.fs.find():
            yield d._id

    def clear(self):
        self.db['fs.files'].drop()
        self.db['fs.chunks'].drop()

    def __str__(self):
        return str(dict(self.items()))

