#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    requests_cache.backends.mongodict
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Dictionary-like objects for saving large data sets to ``mongodb`` database
"""
import pymongo

from collections import MutableMapping
try:
    import cPickle as pickle
except ImportError:
    import pickle

def is_pymongo_v3():
    """
    Determine which version of pymongo is present
    """
    return int(pymongo.version[0]) > 2

def create_mongo_client():
    """
    Create a mongo connection
    """
    if is_pymongo_v3():
        return pymongo.MongoClient()
    else:
        return pymongo.Connection()

class MongoDict(MutableMapping):
    """ MongoDict - a dictionary-like interface for ``mongo`` database
    """
    def __init__(self, db_name,
                 collection_name='mongo_dict_data', connection=None):
        """
        :param db_name: database name (be careful with production databases)
        :param collection_name: collection name (default: mongo_dict_data)
        :param connection: ``pymongo.Connection`` instance. If it's ``None``
                           (default) new connection with default options will
                           be created
        """
        if connection is not None:
            self.connection = connection
        else:
            self.connection = create_mongo_client()
        self.db = self.connection[db_name]
        self.collection = self.db[collection_name]
        self.projection = 'projection' if is_pymongo_v3() else 'fields'

    def __getitem__(self, key):
        result = self.collection.find_one({'_id': key})
        if result is None:
            raise KeyError
        return result['data']

    def __setitem__(self, key, item):
        self.collection.save({'_id': key, 'data': item})

    def __delitem__(self, key):
        spec = {'_id': key}
        if self.collection.find_one(spec, **{self.projection: ['_id']}):
            self.collection.remove(spec)
        else:
            raise KeyError

    def __len__(self):
        return self.collection.count()

    def __iter__(self):
        for d in self.collection.find(**{self.projection: ['_id']}):
            yield d['_id']

    def clear(self):
        self.collection.drop()

    def __str__(self):
        return str(dict(self.items()))

class MongoPickleDict(MongoDict):
    """ Same as :class:`MongoDict`, but pickles values before saving
    """
    def __setitem__(self, key, item):
        super(MongoPickleDict, self).__setitem__(key, pickle.dumps(item))

    def __getitem__(self, key):
        return pickle.loads(bytes(super(MongoPickleDict, self).__getitem__(key)))
