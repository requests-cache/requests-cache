(expiration)=
# {fa}`clock` Expiration
By default, cached responses will be stored indefinitely. There are a number of options for
specifying how long to store responses, either with a single expiration value, glob patterns,
or {ref}`cache headers <headers>`.

The simplest option is to initialize the cache with an `expire_after` value, which will apply to all
reponses:
```python
>>> # Set expiration for the session using a value in seconds
>>> session = CachedSession(expire_after=360)
```

(precedence)=
## Expiration Precedence
Expiration can be set on a per-session, per-URL, or per-request basis, in addition to cache
headers (see sections below for usage details). When there are multiple values provided for a given
request, the following order of precedence is used:
1. Cache-Control response headers (if enabled)
2. Cache-Control request headers
3. Per-request expiration (`expire_after` argument for {py:meth}`.CachedSession.request`)
4. Per-URL expiration (`urls_expire_after` argument for {py:class}`.CachedSession`)
5. Per-session expiration (`expire_after` argument for {py:class}`.CacheBackend`)

## Expiration Values
`expire_after` can be any of the following:
- `-1` (to never expire)
- `0` (to "expire immediately," e.g. bypass the cache)
- A positive number (in seconds)
- A {py:class}`~datetime.timedelta`
- A {py:class}`~datetime.datetime`

Examples:
```python
>>> # To specify a unit of time other than seconds, use a timedelta
>>> from datetime import timedelta
>>> session = CachedSession(expire_after=timedelta(days=30))

>>> # Update an existing session to disable expiration (i.e., store indefinitely)
>>> session.expire_after = -1

>>> # Disable caching by default, unless enabled by other settings
>>> session = CachedSession(expire_after=0)
```

(url-patterns)=
## Expiration With URL Patterns
You can use `urls_expire_after` to set different expiration values based on URL glob patterns.
This allows you to customize caching based on what you know about the resources you're requesting
or how you intend to use them. For example, you might request one resource that gets updated
frequently, another that changes infrequently, and another that never changes. Example:
```python
>>> urls_expire_after = {
...     '*.site_1.com': 30,
...     'site_2.com/resource_1': 60 * 2,
...     'site_2.com/resource_2': 60 * 60 * 24,
...     'site_2.com/static': -1,
... }
>>> session = CachedSession(urls_expire_after=urls_expire_after)
```

**Notes:**
- `urls_expire_after` should be a dict in the format `{'pattern': expire_after}`
- `expire_after` accepts the same types as `CachedSession.expire_after`
- Patterns will match request **base URLs without the protocol**, so the pattern `site.com/resource/`
  is equivalent to `http*://site.com/resource/**`
- If there is more than one match, the first match will be used in the order they are defined
- If no patterns match a request, `CachedSession.expire_after` will be used as a default

(request-errors)=
## Expiration and Error Handling
In some cases, you might cache a response, have it expire, but then encounter an error when
retrieving a new response. If you would like to use expired response data in these cases, use the
`stale_if_error` option.

For example:
```python
>>> # Cache a test response and wait until it's expired
>>> session = CachedSession(stale_if_error=True)
>>> session.get('https://httpbin.org/get', expire_after=1)
>>> time.sleep(1)
```

Afterward, let's say the page has moved and you get a 404, or the site is experiencing downtime and
you get a 500. You will then get the expired cache data instead:
```python
>>> response = session.get('https://httpbin.org/get')
>>> print(response.from_cache, response.is_expired)
True, True
```

In addition to HTTP error codes, `stale_if_error` also applies to python exceptions (typically a
{py:exc}`~requests.RequestException`). See `requests` documentation on
[Errors and Exceptions](https://2.python-requests.org/en/master/user/quickstart/#errors-and-exceptions)
for more details on request errors in general.

## Removing Expired Responses
For better read performance, expired responses won't be removed immediately, but will be removed
(or replaced) the next time they are requested.
:::{tip}
Implementing one or more cache eviction algorithms is being considered. If this is something you are
interested in, please provide feedback via [issues](https://github.com/reclosedev/requests-cache/issues)!
:::

To manually clear all expired responses, use
{py:meth}`.CachedSession.remove_expired_responses`:
```python
>>> session.remove_expired_responses()
```

Or, when using patching:
```python
>>> requests_cache.remove_expired_responses()
```

You can also apply a different `expire_after` to previously cached responses, which will
revalidate the cache with the new expiration time:
```python
>>> session.remove_expired_responses(expire_after=timedelta(days=30))
```
