from typing import Iterable

from redis import Redis, StrictRedis

from ..cache_keys import decode, encode
from . import BaseCache, BaseStorage, get_valid_kwargs


class RedisCache(BaseCache):
    """Redis cache backend.

    Args:
        namespace: redis namespace (default: ``'requests-cache'``)
        connection: Redis connection instance to use instead of creating a new one
        kwargs: Additional keyword arguments for :py:class:`redis.client.Redis`
    """

    def __init__(self, namespace='http_cache', connection: Redis = None, **kwargs):
        super().__init__(**kwargs)
        self.responses = RedisDict(namespace, 'responses', connection=connection, **kwargs)
        self.redirects = RedisDict(
            namespace, 'redirects', connection=self.responses.connection, **kwargs
        )


class RedisDict(BaseStorage):
    """A dictionary-like interface for redis key-value store.

    Notes:
        * In order to deal with how redis stores data/keys, all keys and data are pickled.
        * The actual key name on the redis server will be ``namespace:collection_name``.

    Args:
        namespace: Redis namespace
        collection_name: Name of the Redis hash map
        connection: (optional) Redis connection instance to use instead of creating a new one
        kwargs: Additional keyword arguments for :py:class:`redis.client.Redis`
    """

    def __init__(self, namespace, collection_name='http_cache', connection=None, **kwargs):
        super().__init__(**kwargs)
        connection_kwargs = get_valid_kwargs(Redis, kwargs)
        self.connection = connection or StrictRedis(**connection_kwargs)
        self._self_key = ':'.join([namespace, collection_name])

    def __getitem__(self, key):
        result = self.connection.hget(self._self_key, encode(key))
        if result is None:
            raise KeyError
        return self.serializer.loads(result)

    def __setitem__(self, key, item):
        self.connection.hset(self._self_key, encode(key), self.serializer.dumps(item))

    def __delitem__(self, key):
        if not self.connection.hdel(self._self_key, encode(key)):
            raise KeyError

    def __len__(self):
        return self.connection.hlen(self._self_key)

    def __iter__(self):
        for key in self.connection.hkeys(self._self_key):
            yield decode(key)

    def bulk_delete(self, keys: Iterable[str]):
        """Delete multiple keys from the cache. Does not raise errors for missing keys."""
        if keys:
            self.connection.hdel(self._self_key, *[encode(key) for key in keys])

    def clear(self):
        self.connection.delete(self._self_key)
