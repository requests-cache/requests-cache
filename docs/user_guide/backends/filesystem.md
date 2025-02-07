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

## Limited Cache Size

By default, the size of the cache is not limited.
If you want to make sure caching happens within a certain amount of space, you can set the `maximum_cache_bytes` option:

```python
>>> session = CachedSession('~/http_cache', backend='filesystem', maximum_cache_bytes=200*1024*1024)  # 200MB
```

Parameters:

- `maximum_cache_bytes`: Maximum total size of the cache in bytes.
  Once the cache has reached its maximum size, the oldest responses will be dropped to free up enough space.
- `maximum_file_bytes`: The maximum size of a single file in the cache.
  If a file would get larger, it will not be cached.
  By default, this is the same as `maximum_cache_bytes` as no larger file can be stored anyway.
- `block_bytes`: The size of a block of data on the hard drive.
  In order to really make sure that the size on the hard drive stays below the maximum,
  this can be set to the block size on the hard drive (e.g. `4096` for 4KB).
  A lot of small responses can still use up space.
  This helps ensure you do not run out of blocks on the hard drive.

## Performance and Limitations

- Write performance will vary based on the serializer used, in the range of roughly 1-3ms per write.
- This backend stores response files in a single directory, and does not currently implement fan-out. This means that on most filesystems, storing a very large number of responses will result in reduced performance.

### Parallelization

This backend currently uses a simple threading lock rather than a file lock system, so it is not an ideal choice for highly parallel applications.
Using several sessions or filesystem backends in the same directory (same `cache_name`) can result in race conditions.
Make sure to use the same lock object for all sessions caching in the same filesystem directory.

- If you access the directory only from one process in different sessions, initialize `lock` with the same {py:class}`threading.RLock`.
- If you use [multiprocessing], use a {py:class}`multiprocessing.RLock`.
- If you access the same directory from multiple processes, use a {py:attr}`filelock.FileLock`, see [py-filelock].

[multiprocessing]: https://docs.python.org/3/library/multiprocessing.html
[py-filelock]: https://py-filelock.readthedocs.io/
