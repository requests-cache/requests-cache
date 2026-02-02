(filtering)=
# {fas}`filter` Cache Filtering
In many cases you will want to choose what you want to cache instead of just caching everything. By
default, all **read-only** (`GET` and `HEAD`) **requests with a 200 response code** are cached. A
few options are available to modify this behavior.

```{note}
When using {py:class}`.CachedSession`, any requests that you don't want to cache can also be made
with a regular {py:class}`requests.Session` object, or wrapper functions like
{py:func}`requests.get`, etc.
```

(http-method-filtering)=
## Filter by HTTP Methods
To cache additional HTTP methods, specify them with `allowable_methods`:
```python
>>> session = CachedSession(allowable_methods=('GET', 'POST'))
>>> session.post('https://httpbin.org/post', json={'param': 'value'})
```

For example, some APIs use the `POST` method to request data via a JSON-formatted request body, for
requests that may exceed the max size of a `GET` request. You may also want to cache `POST` requests
if you have a case where you could potentially send the exact same data multiple times.

Method override headers will also be respected. For example, if a server supports the `X-HTTP-Method-Override` header, you may want to cache POST requests that only fetch data
(overridden as GET), but not other POST requests that may create/modify data:
```python
>>> session = CachedSession(allowable_methods=('GET'))
>>> session.post('https://httpbin.org/post', headers={'X-HTTP-Method-Override': 'GET'})
```
:::

## Filter by Status Codes
To cache additional status codes, specify them with `allowable_codes`
```python
>>> session = CachedSession(allowable_codes=(200, 418))
>>> session.get('https://httpbin.org/teapot')
```

(url-filtering)=
## Filter by URLs
You can use {ref}`URL patterns <url-patterns>` to define an allowlist for selective caching, by
using a expiration value of `requests_cache.DO_NOT_CACHE` for non-matching request URLs:
```python
>>> from requests_cache import DO_NOT_CACHE, NEVER_EXPIRE, CachedSession
>>> urls_expire_after = {
...     '*.site_1.com': 30,
...     'site_2.com/static': NEVER_EXPIRE,
...     '*': DO_NOT_CACHE,
... }
>>> session = CachedSession(urls_expire_after=urls_expire_after)
```

Note that the catch-all rule above (`'*'`) will behave the same as setting the session-level
expiration to `0`:
```python
>>> urls_expire_after = {'*.site_1.com': 30, 'site_2.com/static': -1}
>>> session = CachedSession(urls_expire_after=urls_expire_after, expire_after=0)
```

(custom-filtering)=
## Custom Cache Filtering
If you need more advanced behavior for choosing what to cache, you can provide a custom filtering
function via the `filter_fn` param. This can by any function that takes a
{py:class}`requests.Response` object and returns a boolean indicating whether or not that response
should be cached. It will be applied to both new responses (on write) and previously cached
responses (on read):

```python
>>> from sys import getsizeof
>>> from requests_cache import CachedSession

>>> def filter_by_size(response: Response) -> bool:
>>>     """Don't cache responses with a body over 1 MB"""
>>>     return getsizeof(response.content) <= 1024 * 1024

>>> session = CachedSession(filter_fn=filter_by_size)
```

```{note}
`filter_fn()` will be used **in addition to** other filtering options.
```

(read-only)=
## Read-Only Cache
If you want to use existing cached responses, but not write any new ones to the cache, you can use
the `read_only` option:
```python
>>> session = CachedSession()
>>> response = session.get('https://httpbin.org/get')
>>> session = CachedSession(read_only=True)
>>> # Or: session.settings.read_only = True

>>> # Existing cached responses will be read:
>>> response = session.get('https://httpbin.org/get')
>>> print(response.from_cache)
True

>>> # New responses will not be cached:
>>> session.get('https://httpbin.org/json')
>>> print(session.cache.contains(url='https://httpbin.org/json'))
False
>>> response = session.get('https://httpbin.org/json')
>>> print(response.from_cache)
False
