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

## Performance and Limitations
- Write performance will vary based on the serializer used, in the range of roughly 1-3ms per write.
- This backend stores response files in a single directory, and does not currently implement fan-out. This means that on most filesystems, storing a very large number of responses will result in reduced performance.
- This backend currently uses a simple threading lock rather than a file lock system, so it is not an ideal choice for highly parallel applications.
