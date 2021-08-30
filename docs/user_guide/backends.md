(backends)=
# {fa}`database` Backends
![](../_static/sqlite_32px.png)
![](../_static/redis_32px.png)
![](../_static/mongodb_32px.png)
![](../_static/dynamodb_32px.png)
![](../_static/files-json_32px.png)

Several cache backends are included. The default is SQLite, since it's generally the simplest to
use, and requires no extra dependencies or configuration.

See {py:mod}`.requests_cache.backends` for usage details for specific backends.

```{note}
In the rare case that SQLite is not available
(for example, [on Heroku](https://devcenter.heroku.com/articles/sqlite3)), a non-persistent
in-memory cache is used by default.
```

## Backend Dependencies
Most of the other backends require some extra dependencies, listed below.

Backend                                                | Class                      | Alias          | Dependencies
-------------------------------------------------------|----------------------------|----------------|-------------
[SQLite](https://www.sqlite.org)                       | {py:class}`.SQLiteCache`   | `'sqlite'`     |
[Redis](https://redis.io)                              | {py:class}`.RedisCache`    | `'redis'`      | [redis-py](https://github.com/andymccurdy/redis-py)
[MongoDB](https://www.mongodb.com)                     | {py:class}`.MongoCache`    | `'mongodb'`    | [pymongo](https://github.com/mongodb/mongo-python-driver)
[GridFS](https://docs.mongodb.com/manual/core/gridfs/) | {py:class}`.GridFSCache`   | `'gridfs'`     | [pymongo](https://github.com/mongodb/mongo-python-driver)
[DynamoDB](https://aws.amazon.com/dynamodb)            | {py:class}`.DynamoDbCache` | `'dynamodb'`   | [boto3](https://github.com/boto/boto3)
Filesystem                                             | {py:class}`.FileCache`     | `'filesystem'` |
Memory                                                 | {py:class}`.BaseCache`     | `'memory'`     |

## Specifying a Backend
You can specify which backend to use with the `backend` parameter for either {py:class}`.CachedSession`
or {py:func}`.install_cache`. You can specify one by name, using the aliases listed above:
```python
>>> session = CachedSession('my_cache', backend='redis')
```

Or by instance:
```python
>>> backend = RedisCache(host='192.168.1.63', port=6379)
>>> session = CachedSession('my_cache', backend=backend)
```

## Backend Options
The `cache_name` parameter has a different use depending on the backend:

Backend         | Cache name used as
----------------|-------------------
SQLite          | Database path
Redis           | Hash namespace
MongoDB, GridFS | Database name
DynamoDB        | Table name
Filesystem      | Cache directory

Each backend class also accepts optional parameters for the underlying connection. For example,
{py:class}`.SQLiteCache` accepts parameters for {py:func}`sqlite3.connect`:
```python
>>> session = CachedSession('my_cache', backend='sqlite', timeout=30)
```

## Testing Backends
If you just want to quickly try out all of the available backends for comparison,
[docker-compose](https://docs.docker.com/compose/) config is included for all supported services.
First, [install docker](https://docs.docker.com/get-docker/) if you haven't already. Then, run:

:::{tab} Bash (Linux/macOS)
```bash
pip install -U requests-cache[all] docker-compose
curl https://raw.githubusercontent.com/reclosedev/requests-cache/master/docker-compose.yml -O docker-compose.yml
docker-compose up -d
```
:::
:::{tab} Powershell (Windows)
```ps1
pip install -U requests-cache[all] docker-compose
Invoke-WebRequest -Uri https://raw.githubusercontent.com/reclosedev/requests-cache/master/docker-compose.yml -Outfile docker-compose.yml
docker-compose up -d
```
:::

(exporting)=
## Exporting To A Different Backend
If you have cached data that you want to copy or migrate to a different backend, you can do this
with `CachedSession.cache.update()`. For example, if you want to dump the contents of a Redis cache
to JSON files:
```python
>>> src_session = CachedSession('my_cache', backend='redis')
>>> dest_session = CachedSession('~/workspace/cache_dump', backend='filesystem', serializer='json')
>>> dest_session.cache.update(src_session.cache)

>>> # List the exported files
>>> print(dest_session.cache.paths())
'/home/user/workspace/cache_dump/9e7a71a3ff2e.json'
'/home/user/workspace/cache_dump/8a922ff3c53f.json'
```

Or, using backend classes directly:
```python
>>> src_cache = RedisCache()
>>> dest_cache = FileCache('~/workspace/cache_dump', serializer='json')
>>> dest_cache.update(src_cache)
```

(custom-backends)=
## Custom Backends
If the built-in backends don't suit your needs, you can create your own by making subclasses of {py:class}`.BaseCache` and {py:class}`.BaseStorage`:

:::{admonition} Example code
:class: toggle
```python
>>> from requests_cache import CachedSession
>>> from requests_cache.backends import BaseCache, BaseStorage

>>> class CustomCache(BaseCache):
...     """Wrapper for higher-level cache operations. In most cases, the only thing you need
...     to specify here is which storage class(es) to use.
...     """
...     def __init__(self, **kwargs):
...         super().__init__(**kwargs)
...         self.redirects = CustomStorage(**kwargs)
...         self.responses = CustomStorage(**kwargs)

>>> class CustomStorage(BaseStorage):
...     """Dict-like interface for lower-level backend storage operations"""
...     def __init__(self, **kwargs):
...         super().__init__(**kwargs)
...
...     def __getitem__(self, key):
...         pass
...
...     def __setitem__(self, key, value):
...         pass
...
...     def __delitem__(self, key):
...         pass
...
...     def __iter__(self):
...         pass
...
...     def __len__(self):
...         pass
...
...     def clear(self):
...         pass
```
:::

You can then use your custom backend in a {py:class}`.CachedSession` with the `backend` parameter:
```python
>>> session = CachedSession(backend=CustomCache())
```
