(gridfs)=
# GridFS
```{image} ../../_static/mongodb.png
```

[GridFS](https://docs.mongodb.com/manual/core/gridfs/) is a specification for storing large files
in MongoDB.

## Use Cases
Use this backend if you are using MongoDB and expect to store responses **larger than 16MB**. See
{py:mod}`~requests_cache.backends.mongodb` for more general info.

## Usage Example
Initialize with a {py:class}`.GridFSCache` instance:
```python
>>> from requests_cache import CachedSession, GridFSCache
>>> session = CachedSession(backend=GridFSCache())
```

Or by alias:
```python
>>> session = CachedSession(backend='gridfs')
```
