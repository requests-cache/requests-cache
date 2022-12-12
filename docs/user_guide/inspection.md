<!-- TODO: This could use some more details and examples -->
(inspection)=
# {fa}`search` Cache Inspection
Here are some ways to get additional information out of the cache session, backend, and responses:

## Response Details
The following attributes are available on responses:
- `from_cache`: indicates if the response came from the cache
- `cache_key`: The unique identifier used to match the request to the response (see {ref}`matching`
  for details)
- `created_at`: {py:class}`~datetime.datetime` of when the cached response was created or last updated
- `expires`: {py:class}`~datetime.datetime` after which the cached response will expire (see
  {ref}`expiration` for details)
- `is_expired`: indicates if the cached response is expired (if, for example, an old response was returned due to a request error)

Examples:
:::{admonition} Example code
:class: toggle
```python
>>> from requests_cache import CachedSession
>>> session = CachedSession(expire_after=timedelta(days=1))

>>> # Placeholders are added for non-cached responses
>>> response = session.get('http://httpbin.org/get')
>>> print(response.from_cache, response.created_at, response.expires, response.is_expired)
False None None None

>>> # Values will be populated for cached responses
>>> response = session.get('http://httpbin.org/get')
>>> print(response.from_cache, response.created_at, response.expires, response.is_expired)
True 2021-01-01 18:00:00 2021-01-02 18:00:00 False

>>> # Print a response object to get general information about it
>>> print(response)
'request: GET https://httpbin.org/get, response: 200 (308 bytes), created: 2021-01-01 22:45:00 IST, expires: 2021-01-02 18:45:00 IST (fresh)'
```
:::

## Cache Contents
You can use `CachedSession.cache.urls` to see all URLs currently in the cache:
```python
>>> session = CachedSession()
>>> print(session.cache.urls)
['https://httpbin.org/get', 'https://httpbin.org/stream/100']
```

If needed, you can get more details on cached responses via `CachedSession.cache.responses`, which
is a dict-like interface to the cache backend. See {py:class}`.CachedResponse` for a full list of
attributes available.

For example, if you wanted to to see all URLs requested with a specific method:
```python
>>> post_urls = [
...     response.url for response in session.cache.responses.values()
...     if response.request.method == 'POST'
... ]
```

You can also inspect `CachedSession.cache.redirects`, which maps redirect URLs to keys of the
responses they redirect to.


### Filtering responses
Use {py:meth}`.BaseCache.filter` to get responses with optional filters. By default, it returns all
responses except any invalid ones that would raise an exception:
```python
>>> for response in session.cache.filter():
>>>     print(response)
```

Get unexpired responses:
```python
>>> for response in session.cache.filter(expired=False):
>>>     print(response)
```

Get keys for **only** expired responses:
```python
>>> expired_responses = session.cache.filter(valid=False, expired=True)
>>> keys = [response.cache_key for response in expired_responses]
```
