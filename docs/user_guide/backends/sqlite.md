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
it's 'used as the default backend for requests-cache.

## Usage Example
SQLite is the default backend, but if you want to pass extra connection options or just want to be
explicit, initialize your session with a {py:class}`.SQLiteCache` instance:
```python
>>> from requests_cache import CachedSession, SQLiteCache
>>> session = CachedSession(backend=SQLiteCache())
```

Or by alias:
```python
>>> session = CachedSession(backend='sqlite')
```

## Connection Options
This backend accepts any keyword arguments for {py:func}`sqlite3.connect`:
```python
>>> backend = SQLiteCache('http_cache', timeout=30)
>>> session = CachedSession(backend=backend)
```

## Cache Files
- See {ref}`files` for general info on specifying cache paths
- If you specify a name without an extension, the default extension `.sqlite` will be used

### In-Memory Caching
SQLite also supports [in-memory databases](https://www.sqlite.org/inmemorydb.html).
You can enable this (in "shared" memory mode) with the `use_memory` option:
```python
>>> session = CachedSession('http_cache', use_memory=True)
```

Or specify a memory URI with additional options:
```python
>>> session = CachedSession(':file:memdb1?mode=memory')
```

Or just `:memory:`, if you are only using the cache from a single thread:
```python
>>> session = CachedSession(':memory:')
```

## Performance
When working with average-sized HTTP responses (\< 1MB) and using a modern SSD for file storage, you
can expect speeds of around:
- Write: 2-8ms
- Read: 0.2-0.6ms

Of course, this will vary based on hardware specs, response size, and other factors.

## Concurrency
SQLite supports concurrent access, so it is safe to use from a multi-threaded and/or multi-process
application. It supports unlimited concurrent reads. Writes, however, are queued and run in serial,
so if you need to make large volumes of concurrent requests, you may want to consider a different
backend that's specifically made for that kind of workload, like {py:class}`.RedisCache`.

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
    instance. This is fine for short-term caching. For longer-term persistance, you can use an
    [attached EBS volume](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ebs-attaching-volume.html).
