(expiration)=
# {fas}`clock` Expiration
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
`expire_after` can be any of the following time values:
- A positive number (in seconds)
- A {py:class}`~datetime.timedelta`
- A {py:class}`~datetime.datetime`

Or one of the following special values:
- `DO_NOT_CACHE`: Skip both reading from and writing to the cache
- `EXPIRE_IMMEDIATELY`: Consider the response already expired, but potentially usable
- `NEVER_EXPIRE`: Store responses indefinitely

```{note}
A value of 0 or `EXPIRE_IMMEDIATELY` will behave the same as
[`Cache-Control: max-age=0`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control#response_directives).
Depending on other settings and headers, an expired response may either be cached and require
revalidation for each use, or not be cached at all. See {ref}`conditional-requests` for more details.
```

Examples:
```python
>>> from datetime import timedelta
>>> from requests_cache import DO_NOT_CACHE, NEVER_EXPIRE, EXPIRE_IMMEDIATELY, CachedSession

>>> # Specify a simple expiration value in seconds
>>> session = CachedSession(expire_after=60)

>>> # To specify a unit of time other than seconds, use a timedelta
>>> session = CachedSession(expire_after=timedelta(days=30))

>>> # Or expire on a specific date and time
>>> session = CachedSession(expire_after=datetime(2023, 1, 1, 0, 0))

>>> # Update an existing session to store new responses indefinitely
>>> session.settings.expire_after = NEVER_EXPIRE

>>> # Disable caching by default, unless enabled by other settings
>>> session = CachedSession(expire_after=DO_NOT_CACHE)

>>> # Override for a single request: cache the response if it can be revalidated
>>> session.request(expire_after=EXPIRE_IMMEDIATELY)
```

(url-patterns)=
## Expiration With URL Patterns
You can use `urls_expire_after` to set different expiration values based on URL glob patterns:
```python
>>> urls_expire_after = {
...     '*.site_1.com': 30,
...     'site_2.com/resource_1': 60 * 2,
...     'site_2.com/resource_2': 60 * 60 * 24,
...     'site_2.com/static': NEVER_EXPIRE,
... }
>>> session = CachedSession(urls_expire_after=urls_expire_after)
```

**Notes:**
- `urls_expire_after` should be a dict in the format `{'pattern': expire_after}`
- `expire_after` accepts the same types as `CachedSession.settings.expire_after`
- Patterns will match request **base URLs without the protocol**, so the pattern `site.com/resource/`
  is equivalent to `http*://site.com/resource/**`
- If there is more than one match, the first match will be used in the order they are defined
- If no patterns match a request, `CachedSession.settings.expire_after` will be used as a default
- See {ref}`url-filtering` for an example of using `urls_expire_after` as an allowlist

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

Similar to the header `Cache-Control: stale-if-error`, you may also pass time value representing the
maximum staleness you are willing to accept:
```python
# If there is an error on refresh, use a cached response if it expired 5 minutes ago or less
session = CachedSession(stale_if_error=timedelta(minutes=5))
```

In addition to HTTP error codes, `stale_if_error` also applies to python exceptions (typically a
{py:exc}`~requests.RequestException`). See `requests` documentation on
[Errors and Exceptions](https://2.python-requests.org/en/master/user/quickstart/#errors-and-exceptions)
for more details on request errors in general.

(stale-while-revalidate)=
## Asynchronous Revalidation
You can use the `stale_while_revalidate` option to improve performance when refreshing responses.
This will cause an expired cached response to be returned initially, while a non-blocking request is
sent to refresh the response for the next time it's requested.

```{note}
While the corresponding response header `Cache-Control: stale-while-revalidate` only applies to
{ref}`conditional-requests`, requests-cache extends this behavior to other refresh requests as well
(even if a validator is not available).
```

You may either set this to `True` to do this regardless of the cached response's age:
```python
session = CachedSession(stale_while_revalidate=True)
```

Or specify a maximum staleness value you are willing to accept:
```python
# Use a cached response while revalidating, if it expired 5 minutes ago or less
session = CachedSession(stale_while_revalidate=timedelta(minutes=5))
```

## Removing Expired Responses

### Manual Removal
For better read performance, expired responses won't be removed immediately, but will be removed
(or replaced) the next time they are requested.

To manually clear all expired responses, use
{py:meth}`.BaseCache.remove`:
```python
>>> session.cache.remove(expired=True)
```

Or, if you are using {py:func}`.install_cache`:
```python
>>> requests_cache.remove_expired_responses()
```

You can also remove responses older than a certain time:
```python
# Remove responses older than 7 days
session.cache.remove(older_than=timedelta(days=7))
```

Or apply a new expiration value to previously cached responses:
```python
# Reset expiration for all responses to 30 days from now
>>> session.cache.reset_expiration(timedelta(days=30))
```

(ttl)=
### Automatic Removal
The following backends have native TTL support, which can be used to automatically remove expired
responses:
* {py:mod}`DynamoDB <requests_cache.backends.dynamodb>`
* {py:mod}`MongoDB <requests_cache.backends.mongodb>`
* {py:mod}`Redis <requests_cache.backends.redis>`

## Request Options
In addition to the base arguments for {py:func}`requests.request`, requests-cache adds some extra
cache-related arguments. These apply to {py:meth}`.CachedSession.request`,
{py:meth}`.CachedSession.send`, and all HTTP method-specific functions (`get()`, `post()`, etc.).

### Per-Request Expiration
The `expire_after` argument can be used to override the session's expiration for a single request.
```python
>>> session = CachedSession(expire_after=300)
>>> # This request will be cached for 60 seconds, not 300
>>> session.get('https://httpbin.org/get', expire_after=60)
```

### Manual Refresh
If you want to manually refresh a response before it expires, you can use the `refresh` argument.

* This is equivalent to **F5** in most browsers.
* The response will be saved with a new expiration time, according to the normal expiration rules
described above.
* If possible, this will {ref}`revalidate <conditional-requests>` with the server to potentially
  avoid re-downloading an unchanged response.
* To force a refresh (e.g., skip revalidation and always send a new request), use the
  `force_refresh` argument. This is equivalent to **Ctrl-F5** in most browsers.

Example:
```python
>>> response_1 = session.get('https://httpbin.org/get')
>>> response_2 = session.get('https://httpbin.org/get', refresh=True)
>>> assert response_2.from_cache is False
```

### Validation-Only Requests
If you want to always send a conditional request before using a cached response, you can use the
session setting `always_revalidate`:
```python
>>> session = CachedSession(always_revalidate=True)
```

Unlike the `refresh` option, this only affects cached responses with a validator.

### Cache-Only Requests
If you want to only use cached responses without making any real requests, you can use the
`only_if_cached` option. This essentially uses your cache in "offline mode". If a response isn't
cached or is expired, you will get a `504 Not Cached` response instead.
```python
>>> session = CachedSession()
>>> session.cache.clear()
>>> response = session.get('https://httpbin.org/get', only_if_cached=True)
>>> print(response.status_code)
504
>>> response.raise_for_status()
HTTPError: 504 Server Error: Not Cached for url: https://httpbin.org/get
```

You can also combine this with `stale_if_error` to return cached responses even if they are expired.
```python
>>> session = CachedSession(expire_after=1, stale_if_error=True)
>>> session.get('https://httpbin.org/get')
>>> time.sleep(1)

>>> # The response will be cached but expired by this point
>>> response = session.get('https://httpbin.org/get', only_if_cached=True)
>>> print(response.status_code)
200
```
