from pymongo import MongoClient

from .base import BaseCache, BaseStorage


class MongoCache(BaseCache):
    """MongoDB cache backend"""

    def __init__(self, db_name='http_cache', **kwargs):
        """
        :param db_name: database name (default: ``'requests-cache'``)
        :param connection: (optional) ``pymongo.Connection``
        """
        super().__init__(**kwargs)
        self.responses = MongoPickleDict(db_name, collection_name='responses', **kwargs)
        kwargs['connection'] = self.responses.connection
        self.redirects = MongoDict(db_name, collection_name='redirects', **kwargs)


class MongoDict(BaseStorage):
    """A dictionary-like interface for a MongoDB collection"""

    def __init__(self, db_name, collection_name='http_cache', connection=None, **kwargs):
        """
        :param db_name: database name (be careful with production databases)
        :param collection_name: collection name (default: mongo_dict_data)
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
        self.collection = self.db[collection_name]

    def __getitem__(self, key):
        result = self.collection.find_one({'_id': key})
        if result is None:
            raise KeyError
        return result['data']

    def __setitem__(self, key, item):
        doc = {'_id': key, 'data': item}
        self.collection.replace_one({'_id': key}, doc, upsert=True)

    def __delitem__(self, key):
        spec = {'_id': key}
        if hasattr(self.collection, "find_one_and_delete"):
            res = self.collection.find_one_and_delete(spec, {'_id': True})
        else:
            res = self.collection.find_and_modify(spec, remove=True, fields={'_id': True})

        if res is None:
            raise KeyError

    def __len__(self):
        return self.collection.count()

    def __iter__(self):
        for d in self.collection.find({}, {'_id': True}):
            yield d['_id']

    def clear(self):
        self.collection.drop()

    def __str__(self):
        return str(dict(self.items()))


class MongoPickleDict(MongoDict):
    """Same as :class:`MongoDict`, but pickles values before saving"""

    def __setitem__(self, key, item):
        super().__setitem__(key, self.serialize(item))

    def __getitem__(self, key):
        return self.deserialize(super().__getitem__(key))
