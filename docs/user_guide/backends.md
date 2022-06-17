(backends)=
# {fas}`database` Backends
This page contains general information about the cache backends supported by requests-cache.

The default backend is SQLite, since it requires no extra dependencies or configuration, and has
great all-around performance for the most common use cases.

Here is a full list of backends available, and any extra dependencies required:

Backend                                               | Class                      | Alias          | Dependencies
------------------------------------------------------|----------------------------|----------------|----------------------------------------------------------
![](../_static/sqlite_32px.png)     {ref}`sqlite`     | {py:class}`.SQLiteCache`   | `'sqlite'`     |
![](../_static/redis_32px.png)      {ref}`redis`      | {py:class}`.RedisCache`    | `'redis'`      | [redis-py](https://github.com/andymccurdy/redis-py)
![](../_static/mongodb_32px.png)    {ref}`mongodb`    | {py:class}`.MongoCache`    | `'mongodb'`    | [pymongo](https://github.com/mongodb/mongo-python-driver)
![](../_static/mongodb_32px.png)    {ref}`gridfs`     | {py:class}`.GridFSCache`   | `'gridfs'`     | [pymongo](https://github.com/mongodb/mongo-python-driver)
![](../_static/dynamodb_32px.png)   {ref}`dynamodb`   | {py:class}`.DynamoDbCache` | `'dynamodb'`   | [boto3](https://github.com/boto/boto3)
![](../_static/files-json_32px.png) {ref}`filesystem` | {py:class}`.FileCache`     | `'filesystem'` |
![](../_static/memory_32px.png) Memory                | {py:class}`.BaseCache`     | `'memory'`     |

<!-- Hidden ToC tree to add pages to sidebar ToC -->
```{toctree}
:hidden:
:glob: true

backends/*
```

## Choosing a Backend
Here are some general notes on choosing a backend:
* All of the backends perform well enough that they usually won't become a bottleneck until you
  start hitting around **700-1000 requests per second**
* It's recommended to start with SQLite until you have a specific reason to switch
* If/when you encounter limitations with SQLite, the next logical choice is usually Redis
* Each backend has some unique features that make them well suited for specific use cases; see
  individual backend docs for more details

Here are some specific situations where you may want to choose one of the other backends:
* Your application is distributed across multiple machines, without access to a common filesystem
* Your application will make large volumes of concurrent writes (i.e., many nodes/threads/processes caching many different URLs)
* Your application environment only has slower file storage options (like a magnetic drive, or NFS with high latency)
* Your application environment has little or no local storage (like some cloud computing services)
* Your application is already using one of the other backends
* You want to reuse your cached response data outside of requests-cache
* You want to use a specific feature available in one of the other backends

## Specifying a Backend
You can specify which backend to use with the `backend` parameter for either {py:class}`.CachedSession`
or {py:func}`.install_cache`. You can specify one by name, using the aliases listed above:
```python
>>> session = CachedSession('my_cache', backend='redis')
```

Or by instance, which is preferable if you want to pass additional backend-specific options:
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
the {ref}`sqlite` backend accepts parameters for {py:func}`sqlite3.connect`.

## Testing Backends
If you just want to quickly try out all of the available backends for comparison,
[docker-compose](https://docs.docker.com/compose/) config is included for all supported services.
First, [install docker](https://docs.docker.com/get-docker/) if you haven't already. Then, run:

::::{tab-set}

:::{tab-item} Bash (Linux/macOS)
```bash
pip install -U requests-cache[all] docker-compose
curl https://raw.githubusercontent.com/requests-cache/requests-cache/main/docker-compose.yml -O docker-compose.yml
docker-compose up -d
```
:::
:::{tab-item} Powershell (Windows)
```ps1
pip install -U requests-cache[all] docker-compose
Invoke-WebRequest -Uri https://raw.githubusercontent.com/requests-cache/requests-cache/main/docker-compose.yml -Outfile docker-compose.yml
docker-compose up -d
```
:::

::::

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

:::{dropdown} Example
:animate: fade-in-slide-down
:color: primary
:icon: file-code

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
