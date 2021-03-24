from redis import Redis

from .base import BaseCache, BaseStorage


class RedisCache(BaseCache):
    """Redis cache backend.

    Args:
        namespace: redis namespace (default: ``'requests-cache'``)
        connection: (optional) Redis connection instance to use instead of creating a new one
    """

    def __init__(self, namespace='http_cache', **kwargs):
        super().__init__(**kwargs)
        self.responses = RedisDict(namespace, collection_name='responses', **kwargs)
        kwargs['connection'] = self.responses.connection
        self.redirects = RedisDict(namespace, collection_name='redirects', **kwargs)


class RedisDict(BaseStorage):
    """A dictionary-like interface for redis key-value store.

    Notes:
        * In order to deal with how redis stores data/keys, all keys and data are pickled.
        * The actual key name on the redis server will be ``namespace:collection_name``.

    Args:
        namespace: Redis namespace
        collection_name: Name of the Redis hash map
        connection: (optional) Redis connection instance to use instead of creating a new one
    """

    def __init__(self, namespace, collection_name='http_cache', connection=None, **kwargs):
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
