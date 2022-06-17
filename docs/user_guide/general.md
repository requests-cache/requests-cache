(general)=
# {fas}`play-circle` General Usage
There are two main ways of using requests-cache:
- **Sessions:** (recommended) Use {py:class}`.CachedSession` to send your requests
- **Patching:** Globally patch `requests` using {py:func}`.install_cache()`

## Sessions
{py:class}`.CachedSession` can be used as a drop-in replacement for {py:class}`requests.Session`.
Basic usage looks like this:
```python
>>> from requests_cache import CachedSession

>>> session = CachedSession()
>>> session.get('https://httpbin.org/get')
```

Any {py:class}`requests.Session` method can be used (but see {ref}`http-method-filtering` section for
options):
```python
>>> session.request('GET', 'https://httpbin.org/get')
>>> session.head('https://httpbin.org/get')
```

Caching can be temporarily disabled for the session with
{py:meth}`.CachedSession.cache_disabled`:
```python
>>> with session.cache_disabled():
...     session.get('https://httpbin.org/get')
```

The best way to clean up your cache is through {ref}`expiration` settings, but you can also
clear out everything at once with {py:meth}`.BaseCache.clear`:
```python
>>> session.cache.clear()
```

(patching)=
## Patching
In some situations, it may not be possible or convenient to manage your own session object. In those
cases, you can use {py:func}`.install_cache`. This adds fully transparent caching to all `requests`
functions, without the need to modify any existing code:
```python
>>> import requests
>>> import requests_cache

>>> requests_cache.install_cache()
>>> requests.get('https://httpbin.org/get')
```

As well as session methods:
```python
>>> session = requests.Session()
>>> session.get('https://httpbin.org/get')
```

{py:func}`.install_cache` accepts all the same parameters as {py:class}`.CachedSession`:
```python
>>> requests_cache.install_cache(expire_after=360, allowable_methods=('GET', 'POST'))
```

It can be temporarily {py:func}`.enabled`:
```python
>>> with requests_cache.enabled():
...     requests.get('https://httpbin.org/get')  # Will be cached
```

Or temporarily {py:func}`.disabled`:
```python
>>> requests_cache.install_cache()
>>> with requests_cache.disabled():
...     requests.get('https://httpbin.org/get')  # Will not be cached
```

Or completely removed with {py:func}`.uninstall_cache`:
```python
>>> requests_cache.uninstall_cache()
>>> requests.get('https://httpbin.org/get')
```

You can also clear out all responses in the cache with {py:func}`.clear`, and check if
requests-cache is currently installed with {py:func}`.is_installed`.

(monkeypatch-issues)=
### Patching Limitations & Potential Issues
There are some scenarios where patching `requests` with {py:func}`.install_cache` is not ideal:
- When using other libraries that patch {py:class}`requests.Session`
- In a multi-threaded or multiprocess application
- In a library that will be imported by other libraries or applications
- In a larger application that makes requests in several different modules, where it may not be
  obvious what is and isn't being cached

In these cases, consider using {py:class}`.CachedSession` instead.

(settings)=
## Settings
There are a number of settings that affect cache behavior, which are covered in more detail in the following sections:
* {ref}`expiration`
* {ref}`filtering`
* {ref}`matching`

These can all be passed as keyword arguments to {py:class}`.CachedSession` or
{py:func}`.install_cache`. When using a session object, these can also be safely modified at any
time via {py:attr}`.CachedSession.settings`. For example:
```python
>>> from requests_cache import CachedSession

>>> session = CachedSession()
>>> session.settings.expire_after = 360
>>> session.settings.stale_if_error = True
```

Note that this does **not** include backend and serializer settings, which cannot be changed after initialization.
