"""
.. image::
    ../_static/mongodb.png

`GridFS <https://docs.mongodb.com/manual/core/gridfs/>`_ is a specification for storing large files
in MongoDB.

Use Cases
^^^^^^^^^
Use this backend if you are using MongoDB and expect to store responses **larger than 16MB**. See
:py:mod:`~requests_cache.backends.mongodb` for more general info.

API Reference
^^^^^^^^^^^^^
.. automodsumm:: requests_cache.backends.gridfs
   :classes-only:
   :nosignatures:
"""
from logging import getLogger
from threading import RLock

from gridfs import GridFS
from gridfs.errors import CorruptGridFile, FileExists
from pymongo import MongoClient

from .._utils import get_valid_kwargs
from .base import BaseCache, BaseStorage
from .mongodb import MongoDict

logger = getLogger(__name__)


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

    def remove_expired_responses(self, *args, **kwargs):
        with self.responses._lock:
            return super().remove_expired_responses(*args, **kwargs)


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
        self._lock = RLock()

    def __getitem__(self, key):
        try:
            with self._lock:
                result = self.fs.find_one({'_id': key})
                if result is None:
                    raise KeyError
                return self.serializer.loads(result.read())
        except CorruptGridFile as e:
            logger.warning(e, exc_info=True)
            raise KeyError

    def __setitem__(self, key, item):
        value = self.serializer.dumps(item)
        encoding = None if isinstance(value, bytes) else 'utf-8'

        with self._lock:
            try:
                self.fs.delete(key)
                self.fs.put(value, encoding=encoding, **{'_id': key})
            # This can happen because GridFS is not thread-safe for concurrent writes
            except FileExists as e:
                logger.warning(e, exc_info=True)

    def __delitem__(self, key):
        with self._lock:
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
