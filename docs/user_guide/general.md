(general)=
# {fa}`play-circle` General Usage
There are two main ways of using requests-cache:
- **Sessions:** (recommended) Use {py:class}`.CachedSession` to send your requests
- **Patching:** Globally patch `requests` using {py:func}`.install_cache()`

## Sessions
{py:class}`.CachedSession` can be used as a drop-in replacement for {py:class}`requests.Session`.
Basic usage looks like this:
```python
>>> from requests_cache import CachedSession
>>>
>>> session = CachedSession()
>>> session.get('http://httpbin.org/get')
```

Any {py:class}`requests.Session` method can be used (but see {ref}`http-methods` section for
options):
```python
>>> session.request('GET', 'http://httpbin.org/get')
>>> session.head('http://httpbin.org/get')
```

Caching can be temporarily disabled for the session with
{py:meth}`.CachedSession.cache_disabled`:
```python
>>> with session.cache_disabled():
...     session.get('http://httpbin.org/get')
```

The best way to clean up your cache is through {ref}`expiration` settings, but you can also
clear out everything at once with {py:meth}`.BaseCache.clear`:
```python
>>> session.cache.clear()
```

(patching)=
## Patching
In some situations, it may not be possible or convenient to manage your own session object. In those
cases, you can use {py:func}`.install_cache` to add caching to all `requests` functions:
```python
>>> import requests
>>> import requests_cache
>>>
>>> requests_cache.install_cache()
>>> requests.get('http://httpbin.org/get')
```

As well as session methods:
```python
>>> session = requests.Session()
>>> session.get('http://httpbin.org/get')
```

{py:func}`.install_cache` accepts all the same parameters as {py:class}`.CachedSession`:
```python
>>> requests_cache.install_cache(expire_after=360, allowable_methods=('GET', 'POST'))
```

It can be temporarily {py:func}`.enabled`:
```python
>>> with requests_cache.enabled():
...     requests.get('http://httpbin.org/get')  # Will be cached
```

Or temporarily {py:func}`.disabled`:
```python
>>> requests_cache.install_cache()
>>> with requests_cache.disabled():
...     requests.get('http://httpbin.org/get')  # Will not be cached
```

Or completely removed with {py:func}`.uninstall_cache`:
```python
>>> requests_cache.uninstall_cache()
>>> requests.get('http://httpbin.org/get')
```

You can also clear out all responses in the cache with {py:func}`.clear`, and check if
requests-cache is currently installed with {py:func}`.is_installed`.

(monkeypatch-issues)=
### Patching Limitations & Potential Issues
Like any other utility that uses monkey-patching, there are some scenarios where you won't want to
use {py:func}`.install_cache`:
- When using other libraries that patch {py:class}`requests.Session`
- In a multi-threaded or multiprocess application
- In a library that will be imported by other libraries or applications
- In a larger application that makes requests in several different modules, where it may not be
  obvious what is and isn't being cached

In any of these cases, consider using {py:class}`.CachedSession`, the {py:func}`.enabled`
contextmanager, or {ref}`selective-caching`.
