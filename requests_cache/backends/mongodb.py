"""
.. image::
    ../_static/mongodb.png

`MongoDB <https://www.mongodb.com>`_ is a NoSQL document database. It stores data in collections
of documents, which are more flexible and less strictly structured than tables in a relational
database.

Use Cases
^^^^^^^^^
MongoDB scales well and is a good option for larger applications. For raw caching performance,
it is not quite as fast as :py:mod:`~requests_cache.backends.redis`, but may be preferable if you
already have a MongoDB instance you're using for other purposes, or if you find it easier to use.

Expiration
^^^^^^^^^^
MongoDB natively supports TTL, and can automatically remove expired responses from the cache.
Note that this is `not guaranteed to happen immediately
<https://www.mongodb.com/docs/v4.0/core/index-ttl/#timing-of-the-delete-operation>`_. This is the
recommended way to expire responses, and you can leave the session ``expire_after`` as the default
(never expire). Example:

    >>> backend = MongoCache(ttl=3600)
    >>> session = CachedSession('http_cache', backend=backend)

Connection Options
^^^^^^^^^^^^^^^^^^
The MongoDB backend accepts any keyword arguments for :py:class:`pymongo.mongo_client.MongoClient`.
These can be passed via :py:class:`.MongoCache`:

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
from ..serializers import dict_serializer
from . import BaseCache, BaseStorage


class MongoCache(BaseCache):
    """MongoDB cache backend

    Args:
        db_name: Database name
        connection: :py:class:`pymongo.MongoClient` object to reuse instead of creating a new one
        kwargs: Additional keyword arguments for :py:class:`pymongo.mongo_client.MongoClient`
    """

    def __init__(
        self,
        db_name: str = 'http_cache',
        connection: MongoClient = None,
        ttl: int = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.responses = MongoPickleDict(
            db_name,
            collection_name='responses',
            connection=connection,
            ttl=ttl,
            **kwargs,
        )
        self.redirects = MongoDict(
            db_name,
            collection_name='redirects',
            connection=self.responses.connection,
            ttl=ttl,
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

    def __init__(
        self,
        db_name: str,
        collection_name: str = 'http_cache',
        connection: MongoClient = None,
        ttl: int = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        connection_kwargs = get_valid_kwargs(MongoClient, kwargs)
        self.connection = connection or MongoClient(**connection_kwargs)
        self.collection = self.connection[db_name][collection_name]
        # Index will not be recreated if it already exists
        # TODO: If TTL changes, drop and recreate index? Or just document that you need to manually
        # call update_ttl()?
        # TODO: Accept timedelta TTL
        if ttl:
            self.collection.create_index('created_at', expireAfterSeconds=ttl)

    def update_ttl(self, ttl: int = None):
        self.collection.drop_index('created_at')
        if ttl:
            self.collection.create_index('created_at', expireAfterSeconds=ttl)

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
    """Same as :class:`MongoDict`, but serializes values before saving.

    By default, responses are only partially serialized (unstructured into a dict), and stored as a
    document.
    """

    def __init__(
        self,
        db_name: str,
        collection_name: str = 'http_cache',
        connection: MongoClient = None,
        ttl: int = None,
        serializer=None,
        **kwargs,
    ):
        super().__init__(
            db_name,
            collection_name=collection_name,
            connection=connection,
            ttl=ttl,
            serializer=serializer or dict_serializer,
            **kwargs,
        )

    def __setitem__(self, key, item):
        super().__setitem__(key, self.serializer.dumps(item))

    def __getitem__(self, key):
        return self.serializer.loads(super().__getitem__(key))
