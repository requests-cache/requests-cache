(user-guide)=
# User Guide
This section covers the main features of requests-cache.

## Installation
Install with pip:
```
pip install requests-cache
```

Or with Conda, if you prefer:
```
conda install -c conda-forge requests-cache
```

### Requirements
- Requires python 3.6+.
- You may need additional dependencies depending on which backend you want to use. To install with
  extra dependencies for all supported {ref}`user_guide:cache backends`:
  ```
  pip install requests-cache[backends]
  ```

### Optional Setup Steps
- See {ref}`security` for recommended setup steps for more secure cache serialization.
- See {ref}`Contributing Guide <contributing:dev installation>` for setup steps for local development.

## General Usage
There are two main ways of using requests-cache:
- **Sessions:** (recommended) Use {py:class}`.CachedSession` to send your requests
- **Patching:** Globally patch `requests` using {py:func}`.install_cache()`

### Sessions
{py:class}`.CachedSession` can be used as a drop-in replacement for {py:class}`requests.Session`.
Basic usage looks like this:
```python
>>> from requests_cache import CachedSession
>>>
>>> session = CachedSession()
>>> session.get('http://httpbin.org/get')
```

Any {py:class}`requests.Session` method can be used (but see {ref}`user_guide:http methods` section
below for config details):
```python
>>> session.request('GET', 'http://httpbin.org/get')
>>> session.head('http://httpbin.org/get')
```

Caching can be temporarily disabled with {py:meth}`.CachedSession.cache_disabled`:
```python
>>> with session.cache_disabled():
...     session.get('http://httpbin.org/get')
```

The best way to clean up your cache is through {ref}`user_guide:cache expiration`, but you can also
clear out everything at once with {py:meth}`.BaseCache.clear`:
```python
>>> session.cache.clear()
```

### Patching
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

#### Limitations
Like any other utility that uses global patching, there are some scenarios where you won't want to
use {py:func}`.install_cache`:
- In a multi-threaded or multiprocess application
- In an application that uses other packages that extend or modify {py:class}`requests.Session`
- In a package that will be used by other packages or applications

## Cache Backends
Several cache backends are included, which can be selected with
the `backend` parameter for either {py:class}`.CachedSession` or {py:func}`.install_cache`:

- `'sqlite'`: [SQLite](https://www.sqlite.org) database (**default**)
- `'redis'`: [Redis](https://redis.io) cache (requires `redis`)
- `'mongodb'`: [MongoDB](https://www.mongodb.com) database (requires `pymongo`)
- `'gridfs'`: [GridFS](https://docs.mongodb.com/manual/core/gridfs/) collections on a MongoDB database (requires `pymongo`)
- `'dynamodb'`: [Amazon DynamoDB](https://aws.amazon.com/dynamodb) database (requires `boto3`)
- `'filesystem'`: Stores responses as files on the local filesystem
- `'memory'` : A non-persistent cache that just stores responses in memory

A backend can be specified either by name, class or instance:
```python
>>> from requests_cache.backends import RedisCache
>>> from requests_cache import CachedSession

>>> # Backend name
>>> session = CachedSession(backend='redis', namespace='my-cache')

>>> # Backend class
>>> session = CachedSession(backend=RedisCache, namespace='my-cache')

>>> # Backend instance
>>> session = CachedSession(backend=RedisCache(namespace='my-cache'))
```
See {py:mod}`requests_cache.backends` for more backend-specific usage details, and see
{ref}`advanced_usage:custom backends` for details on creating your own implementation.

### Cache Name
The `cache_name` parameter will be used as follows depending on the backend:
- `sqlite`: Database path, e.g `~/.cache/my_cache.sqlite`
- `dynamodb`: Table name
- `mongodb` and `gridfs`: Database name
- `redis`: Namespace, meaning all keys will be prefixed with `'<cache_name>:'`
- `filesystem`: Cache directory

## Cache Options
A number of options are available to modify which responses are cached and how they are cached.

### HTTP Methods
By default, only GET and HEAD requests are cached. To cache additional HTTP methods, specify them
with `allowable_methods`. For example, caching POST requests can be used to ensure you don't send
the same data multiple times:
```python
>>> session = CachedSession(allowable_methods=('GET', 'POST'))
>>> session.post('http://httpbin.org/post', json={'param': 'value'})
```

### Status Codes
By default, only responses with a 200 status code are cached. To cache additional status codes,
specify them with `allowable_codes`"
```python
>>> session = CachedSession(allowable_codes=(200, 418))
>>> session.get('http://httpbin.org/teapot')
```

### Request Parameters
By default, all request parameters are taken into account when caching responses. In some cases,
there may be request parameters that don't affect the response data, for example authentication tokens
or credentials. If you want to ignore specific parameters, specify them with `ignored_parameters`:
```python
>>> session = CachedSession(ignored_parameters=['auth-token'])
>>> # Only the first request will be sent
>>> session.get('http://httpbin.org/get', params={'auth-token': '2F63E5DF4F44'})
>>> session.get('http://httpbin.org/get', params={'auth-token': 'D9FAEB3449D3'})
```

In addition to allowing the cache to ignore these parameters when fetching cached results, these
parameters will also be removed from the cache data, including in the request headers.
This makes `ignored_parameters` a good way to prevent key material or other secrets from being
saved in the cache backend.

### Request Headers
In some cases, different headers may result in different response data, so you may want to cache
them separately. To enable this, use `include_get_headers`:
```python
>>> session = CachedSession(include_get_headers=True)
>>> # Both of these requests will be sent and cached separately
>>> session.get('http://httpbin.org/headers', {'Accept': 'text/plain'})
>>> session.get('http://httpbin.org/headers', {'Accept': 'application/json'})
```

## Cache Expiration
By default, cached responses will be stored indefinitely. There are a number of options for
specifying how long to store responses. The simplest option is to initialize the cache with an
`expire_after` value:
```python
>>> # Set expiration for the session using a value in seconds
>>> session = CachedSession(expire_after=360)
```

### Expiration Precedence
Expiration can be set on a per-session, per-URL, or per-request basis, in addition to cache
headers (see sections below for usage details). When there are multiple values provided for a given
request, the following order of precedence is used:
1. Cache-Control request headers (if enabled)
2. Cache-Control response headers (if enabled)
3. Per-request expiration (`expire_after` argument for {py:meth}`.CachedSession.request`)
4. Per-URL expiration (`urls_expire_after` argument for {py:class}`.CachedSession`)
5. Per-session expiration (`expire_after` argument for {py:class}`.CacheBackend`)

### Expiration Values
`expire_after` can be any of the following:
- `-1` (to never expire)
- `0` (to "expire immediately," e.g. bypass the cache)
- A positive number (in seconds)
- A {py:class}`~datetime.timedelta`
- A {py:class}`~datetime.datetime`

Examples:
```python
> >>> # To specify a unit of time other than seconds, use a timedelta
> >>> from datetime import timedelta
> >>> session = CachedSession(expire_after=timedelta(days=30))
>
> >>> # Update an existing session to disable expiration (i.e., store indefinitely)
> >>> session.expire_after = -1
>
> >>> # Disable caching by default, unless enabled by other settings
> >>> session = CachedSession(expire_after=0)
```

### URL Patterns
You can use `urls_expire_after` to set different expiration values for different requests, based on
URL glob patterns. This allows you to customize caching based on what you know about the resources
you're requesting. For example, you might request one resource that gets updated frequently, another
that changes infrequently, and another that never changes. Example:
```python
>>> urls_expire_after = {
...     '*.site_1.com': 30,
...     'site_2.com/resource_1': 60 * 2,
...     'site_2.com/resource_2': 60 * 60 * 24,
...     'site_2.com/static': -1,
... }
>>> session = CachedSession(urls_expire_after=urls_expire_after)
```

You can also use this to define a cache whitelist, so only the patterns you define will be cached:
```python
>>> urls_expire_after = {
...     '*.site_1.com': 30,
...     'site_2.com/static': -1,
...     '*': 0,  # Every other non-matching URL: do not cache
... }
```

**Notes:**
- `urls_expire_after` should be a dict in the format `{'pattern': expire_after}`
- `expire_after` accepts the same types as `CachedSession.expire_after`
- Patterns will match request **base URLs**, so the pattern `site.com/resource/` is equivalent to
  `http*://site.com/resource/**`
- If there is more than one match, the first match will be used in the order they are defined
- If no patterns match a request, `CachedSession.expire_after` will be used as a default.

### Cache-Control
:::{warning}
This is **not** intended to be a thorough or strict implementation of header-based HTTP caching,
e.g. according to RFC 2616.
:::

Optional support is included for a simplified subset of
[Cache-Control](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control)
and other cache headers in both requests and responses. To enable this behavior, use the
`cache_control` option:
```python
>>> session = CachedSession(cache_control=True)
```

**Supported request headers:**
- `Cache-Control: max-age`: Used as the expiration time in seconds
- `Cache-Control: no-cache`: Skips reading response data from the cache
- `Cache-Control: no-store`: Skips reading and writing response data from/to the cache

**Supported response headers:**
- `Cache-Control: max-age`: Used as the expiration time in seconds
- `Cache-Control: no-store` Skips writing response data to the cache
- `Expires`: Used as an absolute expiration time

**Notes:**
- Unlike a browser or proxy cache, `max-age=0` does not currently clear previously cached responses.
- If enabled, Cache-Control directives will take priority over any other `expire_after` value.
  See {ref}`user_guide:expiration precedence` for the full order of precedence.

### Removing Expired Responses
For better performance, expired responses won't be removed immediately, but will be removed
(or replaced) the next time they are requested. To manually clear all expired responses, use
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

(serializers)=
## Serializers
By default, responses are serialized using {py:mod}`pickle`. Some other options are also available:

:::{note}
These features require python 3.7+ and additional dependencies
:::

### JSON Serializer
Storing responses as JSON gives you the benefit of making them human-readable and editable, in
exchange for a slight reduction in performance. This can be especially useful in combination with
the filesystem backend.

:::{admonition} Example JSON-serialized Response
:class: toggle
```{literalinclude} sample_response.json
:language: JSON
```
:::

You can install the extra dependencies for this serializer with:
```bash
pip install requests-cache[json]
```

### YAML Serializer
YAML is another option if you need a human-readable/editable format, with the same tradeoffs as JSON.

:::{admonition} Example YAML-serialized Response
:class: toggle
```{literalinclude} sample_response.yaml
:language: YAML
```
:::

You can install the extra dependencies for this serializer with:
```bash
pip install requests-cache[yaml]
```

### BSON Serializer
[BSON](https://www.mongodb.com/json-and-bson) is a serialization format originally created for
MongoDB, but it can also be used independently. Compared to JSON, it has better performance
(although still not as fast as `pickle`), and adds support for additional data types. It is not
human-readable, but some tools support reading and editing it directly
(for example, [bson-converter](https://atom.io/packages/bson-converter) for Atom).

You can install the extra dependencies for this serializer with:
```bash
pip install requests-cache[mongo]
```

Or if you would like to use the standalone BSON codec for a different backend, without installing
MongoDB dependencies:
```bash
pip install requests-cache[bson]
```


## Error Handling
In some cases, you might cache a response, have it expire, but then encounter an error when
retrieving a new response. If you would like to use expired response data in these cases, use the
`old_data_on_error` option:
```python
>>> # Cache a test response that will expire immediately
>>> session = CachedSession(old_data_on_error=True)
>>> session.get('https://httpbin.org/get', expire_after=0.001)
>>> time.sleep(0.001)
```

Afterward, let's say the page has moved and you get a 404, or the site is experiencing downtime and
you get a 500. You will then get the expired cache data instead:
```python
>>> response = session.get('https://httpbin.org/get')
>>> print(response.from_cache, response.is_expired)
True, True
```

In addition to error codes, `old_data_on_error` also applies to exceptions (typically a
{py:exc}`~requests.RequestException`). See requests documentation on
[Errors and Exceptions](https://2.python-requests.org/en/master/user/quickstart/#errors-and-exceptions)
for more details on request errors in general.

## Potential Issues
- Version updates of `requests`, `urllib3` or `requests-cache` itself may not be compatible with
  previously cached data (see issues [#56](https://github.com/reclosedev/requests-cache/issues/56)
  and [#102](https://github.com/reclosedev/requests-cache/issues/102)).
  The best way to prevent this is to use a virtualenv and pin your dependency versions.
- See {ref}`security` for notes on serialization security
