(filesystem)=
# Filesystem
```{image} ../../_static/files-generic.png
```

This backend stores responses in files on the local filesystem, with one file per response.

## Use Cases
This backend is useful if you would like to use your cached response data outside of requests-cache,
for example:

- Manually viewing cached responses without the need for extra tools (e.g., with a simple text editor)
- Using cached responses as sample data for automated tests
- Reading cached responses directly from another application or library, without depending on requests-cache

## Usage Example
Initialize with a {py:class}`.FileCache` instance:
```python
>>> from requests_cache import CachedSession, FileCache
>>> session = CachedSession(backend=FileCache())
```

Or by alias:
```python
>>> session = CachedSession(backend='filesystem')
```

## File Formats
By default, responses are saved as JSON files. If you prefer a different format, you can use of the
other available {ref}`serializers` or provide your own. For example, to save responses as
YAML files (requires `pyyaml`):
```python
>>> session = CachedSession('~/http_cache', backend='filesystem', serializer='yaml')
>>> session.get('https://httpbin.org/get')
```

## Cache Files
- See {ref}`files` for general info on specifying cache paths
- The path for a given response will be in the format `<cache_name>/<cache_key>`
- Redirects are stored in a separate SQLite database, located at `<cache_name>/redirects.sqlite`
- Use {py:meth}`.FileCache.paths` to get a list of all cached response paths:
```python
>>> print(list(session.cache.paths()))
> ['/home/user/http_cache/4dc151d95200ec.yaml']
```

## Limiting Cache Size
If you want to limit the size of the cache, you can enable LRU caching with the `max_cache_bytes` option:

```python
>>> session = CachedSession(
...     '~/http_cache',
...       backend='filesystem',
...       max_cache_bytes=200*1024*1024, # 200MB
... )
```

When the cache reaches the specified size, the least recently used file(s) will be deleted until the cache is back under the limit.

Files larger than this will not be cached. To reduce the size limit for individual files, use the `max_file_bytes` option.

```{note}
Note on accurate file size tracking: Files on disk are stored in blocks, so the actual size on disk may be larger than the raw file size. To ensure that the real disk usage stays below the maximum, you can set the `block_bytes` parameter to the block size of your filesystem. 4KB is a common size, for example, so you could set `block_bytes=4096`.
```

Example with all LRU-related options:
```python

```python
>>> session = CachedSession(
...     '~/http_cache',
...       backend='filesystem',
...       max_cache_bytes=200*1024*1024, # 200MB
...       max_file_bytes=50*1024*1024,   # 50MB
...       block_bytes=4096,              # 4KB blocks
...       sync_index=True,               # Check for manual changes on disk since last use
... )
```
```

## Performance and Limitations

- Write performance will vary based on the serializer used, in the range of roughly 1-3ms per write.
- This backend stores response files in a single directory, and does not currently implement fan-out. This means that on most filesystems, storing a very large number of responses will result in reduced performance.

### Parallelization

This backend currently uses a simple threading lock rather than a file lock system, so it is not an ideal choice for highly parallel applications.
If you use multiple cache objects in the same directory, use a shared {py:class}`threading.RLock` for all of them using the `lock` parameter:
```python
>>> import threading
>>> lock = threading.RLock()
>>> session1 = CachedSession(backend='filesystem', cache_name='cache_dir', lock=lock)
>>> session2 = CachedSession(backend='filesystem', cache_name='cache_dir', lock=lock)
```

- If you're using the {py:mod}`.multiprocessing` module, use a {py:class}`multiprocessing.RLock` instead.
- If you're using multiple processes by other means, use a {py:attr}`filelock.FileLock` from the [py-filelock](https://py-filelock.readthedocs.io/) library.
