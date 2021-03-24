#!/usr/bin/env python
"""
    requests_cache.backends.redisdict
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Dictionary-like objects for saving large data sets to ``redis`` key-store
"""
from redis import StrictRedis as Redis

from ..base import BaseStorage


class RedisDict(BaseStorage):
    """A dictionary-like interface for redis key-value store"""

    def __init__(self, namespace, collection_name='redis_dict_data', connection=None, **kwargs):
        """
        The actual key name on the redis server will be
        ``namespace``:``collection_name``

        In order to deal with how redis stores data/keys,
        everything, i.e. keys and data, must be pickled.

        :param namespace: namespace to use
        :param collection_name: name of the hash map stored in redis
                                (default: redis_dict_data)
        :param connection: ``redis.StrictRedis`` instance.
                           If it's ``None`` (default), a new connection with
                           default options will be created

        """
        super().__init__(**kwargs)
        if connection is not None:
            self.connection = connection
        else:
            self.connection = Redis()
        self._self_key = ':'.join([namespace, collection_name])

    def __getitem__(self, key):
        result = self.connection.hget(self._self_key, self.serialize(key))
        if result is None:
            raise KeyError
        return self.deserialize(result)

    def __setitem__(self, key, item):
        self.connection.hset(self._self_key, self.serialize(key), self.serialize(item))

    def __delitem__(self, key):
        if not self.connection.hdel(self._self_key, self.serialize(key)):
            raise KeyError

    def __len__(self):
        return self.connection.hlen(self._self_key)

    def __iter__(self):
        for v in self.connection.hkeys(self._self_key):
            yield self.deserialize(v)

    def clear(self):
        self.connection.delete(self._self_key)

    def __str__(self):
        return str(dict(self.items()))
