"""
.. image::
    ../_static/mongodb.png

`GridFS <https://docs.mongodb.com/manual/core/gridfs/>`_ is a specification for storing large files
(>16 MB) in MongoDB. See :py:mod:`~requests_cache.backends.mongodb` for more general info on MongoDB.

API Reference
^^^^^^^^^^^^^
.. automodsumm:: requests_cache.backends.gridfs
   :classes-only:
   :nosignatures:
"""
from gridfs import GridFS
from pymongo import MongoClient

from .._utils import get_valid_kwargs
from .base import BaseCache, BaseStorage
from .mongodb import MongoDict


class GridFSCache(BaseCache):
    """GridFS cache backend.

    Example:

        >>> session = CachedSession('http_cache', backend='gridfs')

    Args:
        db_name: Database name
        connection: :py:class:`pymongo.MongoClient` object to reuse instead of creating a new one
        kwargs: Additional keyword arguments for :py:class:`pymongo.MongoClient`
    """

    def __init__(self, db_name: str, **kwargs):
        super().__init__(**kwargs)
        self.responses = GridFSPickleDict(db_name, **kwargs)
        self.redirects = MongoDict(
            db_name, collection_name='redirects', connection=self.responses.connection, **kwargs
        )


class GridFSPickleDict(BaseStorage):
    """A dictionary-like interface for a GridFS database

    Args:
        db_name: Database name
        collection_name: Ignored; GridFS internally uses collections 'fs.files' and 'fs.chunks'
        connection: :py:class:`pymongo.MongoClient` object to reuse instead of creating a new one
        kwargs: Additional keyword arguments for :py:class:`pymongo.MongoClient`
    """

    def __init__(self, db_name, collection_name=None, connection=None, **kwargs):
        super().__init__(**kwargs)
        connection_kwargs = get_valid_kwargs(MongoClient, kwargs)
        self.connection = connection or MongoClient(**connection_kwargs)
        self.db = self.connection[db_name]
        self.fs = GridFS(self.db)

    def __getitem__(self, key):
        result = self.fs.find_one({'_id': key})
        if result is None:
            raise KeyError
        return self.serializer.loads(result.read())

    def __setitem__(self, key, item):
        try:
            self.__delitem__(key)
        except KeyError:
            pass
        value = self.serializer.dumps(item)
        encoding = None if isinstance(value, bytes) else 'utf-8'
        self.fs.put(value, encoding=encoding, **{'_id': key})

    def __delitem__(self, key):
        res = self.fs.find_one({'_id': key})
        if res is None:
            raise KeyError
        self.fs.delete(res._id)

    def __len__(self):
        return self.db['fs.files'].estimated_document_count()

    def __iter__(self):
        for d in self.fs.find():
            yield d._id

    def clear(self):
        self.db['fs.files'].drop()
        self.db['fs.chunks'].drop()
