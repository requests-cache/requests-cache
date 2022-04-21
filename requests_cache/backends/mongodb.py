"""
.. image::
    ../_static/mongodb.png

`MongoDB <https://www.mongodb.com>`_ is a NoSQL document database. It stores data in collections
of documents, which are more flexible and less strictly structured than tables in a relational
database.

Connection Options
^^^^^^^^^^^^^^^^^^
The MongoDB backend accepts any keyword arguments for :py:class:`pymongo.mongo_client.MongoClient`:

    >>> backend = MongoCache(host='192.168.1.63', port=27017)
    >>> session = CachedSession('http_cache', backend=backend)

API Reference
^^^^^^^^^^^^^
.. automodsumm:: requests_cache.backends.mongodb
   :classes-only:
   :nosignatures:
"""
from typing import Iterable

from pymongo import MongoClient

from .._utils import get_valid_kwargs
from . import BaseCache, BaseStorage


class MongoCache(BaseCache):
    """MongoDB cache backend

    Args:
        db_name: Database name
        connection: :py:class:`pymongo.MongoClient` object to reuse instead of creating a new one
        kwargs: Additional keyword arguments for :py:class:`pymongo.mongo_client.MongoClient`
    """

    def __init__(self, db_name: str = 'http_cache', connection: MongoClient = None, **kwargs):
        super().__init__(**kwargs)
        self.responses = MongoPickleDict(db_name, 'responses', connection=connection, **kwargs)
        self.redirects = MongoDict(
            db_name,
            collection_name='redirects',
            connection=self.responses.connection,
            **kwargs,
        )


class MongoDict(BaseStorage):
    """A dictionary-like interface for a MongoDB collection

    Args:
        db_name: Database name
        collection_name: Collection name
        connection: :py:class:`pymongo.MongoClient` object to reuse instead of creating a new one
        kwargs: Additional keyword arguments for :py:class:`pymongo.MongoClient`
    """

    def __init__(self, db_name, collection_name='http_cache', connection=None, **kwargs):
        super().__init__(**kwargs)
        connection_kwargs = get_valid_kwargs(MongoClient.__init__, kwargs)
        self.connection = connection or MongoClient(**connection_kwargs)
        self.collection = self.connection[db_name][collection_name]

    def __getitem__(self, key):
        result = self.collection.find_one({'_id': key})
        if result is None:
            raise KeyError
        return result['data']

    def __setitem__(self, key, item):
        doc = {'_id': key, 'data': item}
        self.collection.replace_one({'_id': key}, doc, upsert=True)

    def __delitem__(self, key):
        result = self.collection.find_one_and_delete({'_id': key}, {'_id': True})
        if result is None:
            raise KeyError

    def __len__(self):
        return self.collection.estimated_document_count()

    def __iter__(self):
        for d in self.collection.find({}, {'_id': True}):
            yield d['_id']

    def bulk_delete(self, keys: Iterable[str]):
        """Delete multiple keys from the cache. Does not raise errors for missing keys."""
        self.collection.delete_many({'_id': {'$in': list(keys)}})

    def clear(self):
        self.collection.drop()


class MongoPickleDict(MongoDict):
    """Same as :class:`MongoDict`, but pickles values before saving"""

    def __setitem__(self, key, item):
        super().__setitem__(key, self.serializer.dumps(item))

    def __getitem__(self, key):
        return self.serializer.loads(super().__getitem__(key))
