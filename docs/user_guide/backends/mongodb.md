(mongodb)=
# MongoDB
```{image} ../../_static/mongodb.png
```

[MongoDB](https://www.mongodb.com) is a NoSQL document database. It stores data in collections
of documents, which are more flexible and less strictly structured than tables in a relational
database.

## Use Cases
MongoDB scales well and is a good option for larger applications. For raw caching performance, it is
not quite as fast as {py:mod}`~requests_cache.backends.redis`, but may be preferable if you already
have an instance running, or if it has a specific feature you want to use. See sections below for
some relevant examples.

## Usage Example
Initialize with a {py:class}`.MongoCache` instance:
```python
>>> from requests_cache import CachedSession, MongoCache
>>> session = CachedSession(backend=MongoCache())
```

Or by alias:
```python
>>> session = CachedSession(backend='mongodb')
```

## Connection Options
This backend accepts any keyword arguments for {py:class}`pymongo.mongo_client.MongoClient`:
```python
>>> backend = MongoCache(host='192.168.1.63', port=27017)
>>> session = CachedSession('http_cache', backend=backend)
```

## Viewing Responses
By default, responses are only partially serialized so they can be saved as plain MongoDB documents.
Response data can be easily viewed via the
[MongoDB shell](https://www.mongodb.com/docs/mongodb-shell/#mongodb-binary-bin.mongosh),
[Compass](https://www.mongodb.com/products/compass), or any other interface for MongoDB.

Here is an example response viewed in
[MongoDB for VSCode](https://code.visualstudio.com/docs/azure/mongodb):

:::{dropdown} Screenshot
:animate: fade-in-slide-down
:color: primary
:icon: file-media
```{image} ../../_static/mongodb_vscode.png
```
:::

## Expiration
MongoDB [natively supports TTL](https://www.mongodb.com/docs/v4.0/core/index-ttl), and can
automatically remove expired responses from the cache.

**Notes:**
- TTL is set for a whole collection, and cannot be set on a per-document basis.
- It will persist until explicitly removed or overwritten, or if the collection is deleted.
- Expired items are
  [not guaranteed to be removed immediately](https://www.mongodb.com/docs/v4.0/core/index-ttl/#timing-of-the-delete-operation).
  Typically it happens within 60 seconds.
- If you want, you can rely entirely on MongoDB TTL instead of requests-cache
  {ref}`expiration settings <expiration>`.
- Or you can set both values, to be certain that you don't get an expired response before MongoDB
  removes it.
- If you intend to reuse expired responses, e.g. with {ref}`conditional-requests` or `stale_if_error`,
  you can set TTL to a larger value than your session `expire_after`, or disable it altogether.

**Examples:**
Create a TTL index:
```python
>>> backend = MongoCache()
>>> backend.set_ttl(3600)
```

Overwrite it with a new value:
```python
>>> backend = MongoCache()
>>> backend.set_ttl(timedelta(days=1), overwrite=True)
```

Remove the TTL index:
```python
>>> backend = MongoCache()
>>> backend.set_ttl(None, overwrite=True)
```

Use both MongoDB TTL and requests-cache expiration:
```python
>>> ttl = timedelta(days=1)
>>> backend = MongoCache()
>>> backend.set_ttl(ttl)
>>> session = CachedSession(backend=backend, expire_after=ttl)
```

**Recommended:** Set MongoDB TTL to a longer value than your {py:class}`.CachedSession` expiration.
This allows expired responses to be eventually cleaned up, but still be reused for conditional
requests for some period of time:
```python
>>> backend = MongoCache()
>>> backend.set_ttl(timedelta(days=7))
>>> session = CachedSession(backend=backend, expire_after=timedelta(days=1))
```
