(sqlite)=
# SQLite
```{image} ../../_static/sqlite.png
```
[SQLite](https://www.sqlite.org/) is a fast and lightweight SQL database engine that stores data
either in memory or in a single file on disk.

## Use Cases
Despite its simplicity, SQLite is a powerful tool. For example, it's the primary storage system for
a number of common applications including Firefox, Chrome, and many components of both Android and
iOS. It's well suited for caching, and requires no extra configuration or dependencies, which is why
it's used as the default backend for requests-cache.

## Usage Example
SQLite will be used as the default backend without providing any arguments. If you want to pass
extra connection options or just want to be explicit, initialize your session with a
{py:class}`.SQLiteCache` instance:
```python
>>> from requests_cache import CachedSession, SQLiteCache
>>> backend = SQLiteCache()
>>> session = CachedSession(backend=backend)
```

Or initialize it by alias:
```python
>>> session = CachedSession(backend='sqlite')
```

## Connection Options
This backend accepts any keyword arguments for {py:func}`sqlite3.connect`:
```python
>>> backend = SQLiteCache(timeout=30)
```

## Cache Files
- By default, a file named `http_cache.sqlite` will be created in the current working directory
- You can specify a different cache filename using the first positional argument to {py:class}`.SQLiteCache`
- If you specify a name without an extension, the default extension `.sqlite` will be used
- See {ref}`files` for general info on specifying cache paths

Example
```python
>>> backend = SQLiteCache('cache/http_cache.sqlite')
```

### In-Memory Caching
SQLite also supports [in-memory databases](https://www.sqlite.org/inmemorydb.html).
You can enable this (in "shared" memory mode) with the `use_memory` option:
```python
>>> backend = SQLiteCache(use_memory=True)
```

Or specify a memory URI with additional options:
```python
>>> backend = SQLiteCache(':file:memdb1?mode=memory')
```

Or just `:memory:`, if you are only using the cache from a single thread:
```python
>>> backend = SQLiteCache(':memory:')
```

## Performance
When working with average-sized HTTP responses (\< 1MB) and using a modern SSD for file storage, you
can expect speeds of around:
- Write: 2-8ms
- Read: 0.2-0.6ms

Of course, this will vary based on hardware specs, response size, and other factors.

The `fast_save` option can be used to increase cache write performance, but with the possibility of
data loss. See `pragma: synchronous <https://www.sqlite.org/pragma.html#pragma_synchronous>`_
for details.
```python
>>> backend = SQLiteCache(fast_save=True)
```

## Concurrency
SQLite supports concurrent access, so it is safe to use from a multi-threaded and/or multi-process
application. It supports unlimited concurrent reads. Writes, however, are queued and run in serial,
so if you need to make large volumes of concurrent requests, you may want to consider a different
backend that's specifically made for that kind of workload, like {py:class}`.RedisCache`.

One option to consider is `Write Ahead Logging <https://sqlite.org/wal.html>`_. This comes with a
number of tradeoffs, but most notably it allows read operations to not block writes. This can be
enabled with the `wal` option:
```python
>>> backend = SQLiteCache(wal=True)
```

## Hosting Services and Filesystem Compatibility
There are some caveats to using SQLite with some hosting services, based on what kind of storage is
available:

- NFS:
  - SQLite may be used on a NFS, but is usually only safe to use from a single process at a time.
    See the [SQLite FAQ](https://www.sqlite.org/faq.html#q5) for details.
  - PythonAnywhere is one example of a host that uses NFS-backed storage. Using SQLite from a
    multiprocess application will likely result in `sqlite3.OperationalError: database is locked`.
- Ephemeral storage:
  - Heroku [explicitly disables SQLite](https://devcenter.heroku.com/articles/sqlite3) on its dynos.
  - AWS [EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/InstanceStorage.html),
    [Lambda (depending on configuration)](https://aws.amazon.com/blogs/compute/choosing-between-aws-lambda-data-storage-options-in-web-apps/),
    and some other AWS services use ephemeral storage that only persists for the lifetime of the
    instance. This is fine for short-term caching. For longer-term persistance, you can store the
    cache on an
    [attached EBS volume](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-attaching-volume.html).
