(redis)=
# Redis
```{image} ../../_static/redis.png
```

[Redis](https://redis.io) is an in-memory data store with on-disk persistence.

## Use Cases
Redis offers a high-performace cache that scales exceptionally well, making it an ideal choice for
larger applications, especially those that make a large volume of concurrent requests.

## Usage Example
Initialize your session with a {py:class}`.RedisCache` instance:
```python
>>> from requests_cache import CachedSession, RedisCache
>>> session = CachedSession(backend=RedisCache())
```

Or by alias:
```python
>>> session = CachedSession(backend='redis')
```

## Connection Options
This backend accepts any keyword arguments for {py:class}`redis.client.Redis`:
```python
>>> backend = RedisCache(host='192.168.1.63', port=6379)
>>> session = CachedSession('http_cache', backend=backend)
```

Or you can pass an existing `Redis` object:
```python
>>> from redis import Redis

>>> connection = Redis(host='192.168.1.63', port=6379)
>>> backend = RedisCache(connection=connection))
>>> session = CachedSession('http_cache', backend=backend)
```

## Persistence
Redis operates on data in memory, and by default also persists data to snapshots on disk. This is
optimized for performance, with a minor risk of data loss, and is usually the best configuration
for a cache. If you need different behavior, the frequency and type of persistence can be customized
or disabled entirely. See [Redis Persistence](https://redis.io/topics/persistence) for details.

## Expiration
Redis natively supports TTL on a per-key basis, and can automatically remove expired responses from
the cache. This will be set by by default, according to normal {ref}`expiration settings <expiration>`.
See [Redis: EXPIRE](https://redis.io/commands/expire/) docs for more details on internal TTL behavior.

If you intend to reuse expired responses, e.g. with {ref}`conditional-requests` or `stale_if_error`,
you can use the `ttl_offset` argument to add additional time before deletion (default: 1 hour).
In other words, this makes backend expiration longer than cache expiration:
```python
>>> backend = RedisCache(ttl_offset=3600)
```

Alternatively, you can disable TTL completely with the `ttl` argument:
```python
>>> backend = RedisCache(ttl=False)
```

## Redislite
If you can't easily set up your own Redis server, another option is
[redislite](https://github.com/yahoo/redislite). It contains its own lightweight, embedded Redis
database, and can be used as a drop-in replacement for redis-py. Usage example:
```python
>>> from redislite import Redis
>>> from requests_cache import CachedSession, RedisCache

>>> backend = RedisCache(connection=Redis())
>>> session = CachedSession(backend=backend)
```
