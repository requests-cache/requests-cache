"""
.. image::
    ../_static/redis.png

`Redis <https://redis.io>`_ is an in-memory data structure store with on-disk persistence.
It offers a high-performace cache that scales exceptionally well, making it an ideal choice for
larger applications.

Connection Options
^^^^^^^^^^^^^^^^^^
The Redis backend accepts any keyword arguments for :py:class:`redis.client.Redis`. These can be passed
via :py:class:`.CachedSession`:

    >>> session = CachedSession('http_cache', backend='redis', host='192.168.1.63', port=6379)

Or via :py:class:`.RedisCache`:

    >>> backend = RedisCache(host='192.168.1.63', port=6379)
    >>> session = CachedSession('http_cache', backend=backend)

API Reference
^^^^^^^^^^^^^
.. automodsumm:: requests_cache.backends.redis
   :classes-only:
   :nosignatures:
"""
from typing import Iterable

from redis import Redis, StrictRedis

from ..cache_keys import decode, encode
from . import BaseCache, BaseStorage, get_valid_kwargs


class RedisCache(BaseCache):
    """Redis cache backend

    Args:
        namespace: Redis namespace
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
    """A dictionary-like interface for Redis operations

    **Notes:**
        * In order to deal with how Redis stores data, all keys will be encoded and all values will
          be serialized.
        * The full hash name will be ``namespace:collection_name``
    """

    def __init__(self, namespace, collection_name='http_cache', connection=None, **kwargs):
        super().__init__(**kwargs)
        connection_kwargs = get_valid_kwargs(Redis, kwargs)
        self.connection = connection or StrictRedis(**connection_kwargs)
        self._self_key = f'{namespace}:{collection_name}'

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
