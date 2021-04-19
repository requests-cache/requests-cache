from gridfs import GridFS
from pymongo import MongoClient

from .base import BaseCache, BaseStorage
from .mongo import MongoDict


class GridFSCache(BaseCache):
    """GridFS cache backend.
    Use this backend to store documents greater than 16MB.

    Usage:
        requests_cache.install_cache(backend='gridfs')

    Or:
        from pymongo import MongoClient
        requests_cache.install_cache(backend='gridfs', connection=MongoClient('another-host.local'))
    """

    def __init__(self, db_name, **kwargs):
        """
        :param db_name: database name
        :param connection: (optional) ``pymongo.Connection``
        """
        super().__init__(**kwargs)
        self.responses = GridFSPickleDict(db_name, **kwargs)
        kwargs['connection'] = self.responses.connection
        self.redirects = MongoDict(db_name, collection_name='redirects', **kwargs)


class GridFSPickleDict(BaseStorage):
    """A dictionary-like interface for a GridFS collection"""

    def __init__(self, db_name, collection_name=None, connection=None, **kwargs):
        """
        :param db_name: database name (be careful with production databases)
        :param connection: ``pymongo.Connection`` instance. If it's ``None``
                           (default) new connection with default options will
                           be created
        """
        super().__init__(**kwargs)
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
        return self.deserialize(result.read())

    def __setitem__(self, key, item):
        try:
            self.__delitem__(key)
        except KeyError:
            pass
        self.fs.put(self.serialize(item), **{'_id': key})

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

    def __str__(self):
        return str(dict(self.items()))
