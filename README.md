# Requests-Cache
[![Build](https://github.com/reclosedev/requests-cache/actions/workflows/build.yml/badge.svg)](https://github.com/reclosedev/requests-cache/actions/workflows/build.yml)
[![Coverage](https://coveralls.io/repos/github/reclosedev/requests-cache/badge.svg?branch=master)](https://coveralls.io/github/reclosedev/requests-cache?branch=master)
[![Documentation](https://img.shields.io/readthedocs/requests-cache/latest)](https://requests-cache.readthedocs.io/en/latest/)
[![PyPI](https://img.shields.io/pypi/v/requests-cache?color=blue)](https://pypi.org/project/requests-cache)
[![PyPI - Python Versions](https://img.shields.io/pypi/pyversions/requests-cache)](https://pypi.org/project/requests-cache)
[![PyPI - Format](https://img.shields.io/pypi/format/requests-cache?color=blue)](https://pypi.org/project/requests-cache)
[![Code Shelter](https://www.codeshelter.co/static/badges/badge-flat.svg)](https://www.codeshelter.co/)

## Summary
**Requests-cache** is a transparent persistent HTTP cache for the python [requests](http://python-requests.org)
library. It is especially useful for web scraping, consuming REST APIs, slow or rate-limited
sites, or any other scenario in which you're making lots of requests that are likely to be sent
more than once.

Several storage backends are included: **SQLite**, **Redis**, **MongoDB**, and **DynamoDB**.

See full project documentation at: https://requests-cache.readthedocs.io

## Installation
Install with pip:
```bash
pip install requests-cache
```

**Requirements:**
* Requires python 3.6+.
* You may need additional dependencies depending on which backend you want to use. To install with
  extra dependencies for all supported backends:

    ```bash
    pip install requests-cache[backends]
    ```

**Optional Setup Steps:**
* See [Security](https://requests-cache.readthedocs.io/en/latest/security.html) for recommended
  setup for more secure cache serialization.
* See [Contributing Guide](https://requests-cache.readthedocs.io/en/latest/contributing.html)
  for setup info for local development.

## General Usage
There are two main ways of using `requests-cache`:
* **Sessions:** Use [requests_cache.CachedSession](https://requests-cache.readthedocs.io/en/latest/api.html#requests_cache.core.CachedSession)
  in place of [requests.Session](https://requests.readthedocs.io/en/master/user/advanced/#session-objects) (recommended)
* **Patching:** Globally patch `requests` using
  [requests_cache.install_cache](https://requests-cache.readthedocs.io/en/latest/api.html#requests_cache.core.install_cache)

### Sessions
`CachedSession` wraps `requests.Session` with caching features, and otherwise behaves the same as a
normal session.

Basic example:
```python
from requests_cache import CachedSession

session = CachedSession('demo_cache', backend='sqlite')
for i in range(100):
    session.get('http://httpbin.org/delay/1')
```
The URL in this example adds a delay of 1 second, but all 100 requests will complete in just over 1
second. The response will be fetched once, saved to `demo_cache.sqlite`, and subsequent requests
will return the cached response near-instantly.

### Patching
Patching with `requests_cache.install_cache()` will add caching to all `requests` functions:
```python
import requests
import requests_cache

requests_cache.install_cache()
requests.get('http://httpbin.org/get')
session = requests.Session()
session.get('http://httpbin.org/get')
```

`install_cache()` takes all the same parameters as `CachedSession`. It can be temporarily disabled
with `disabled()`, and completely removed with `uninstall_cache()`:
```python
# Neither of these requests will use the cache
with requests_cache.disabled():
    requests.get('http://httpbin.org/get')

requests_cache.uninstall_cache()
requests.get('http://httpbin.org/get')
```

**Limitations:**

Like any other utility that uses global patching, there are some scenarios where you won't want to
use this:
* In a multi-threaded or multiprocess applications
* In an application that uses other packages that extend or modify `requests.Session`
* In a package that will be used by other packages or applications

### Cache Backends
Several cache backends are included, which can be selected with the `backend` parameter to
`CachedSession` or `install_cache()`:

* `'memory'` : Not persistent, just stores responses with an in-memory dict
* `'sqlite'` : [SQLite](https://www.sqlite.org) database (**default**)
* `'redis'` : [Redis](https://redis.io/) cache (requires `redis`)
* `'mongodb'` : [MongoDB](https://www.mongodb.com/) database (requires `pymongo`)
* `'dynamodb'` : [Amazon DynamoDB](https://aws.amazon.com/dynamodb/) database (requires `boto3`)

### Cache Expiration
By default, cached responses will be stored indefinitely. There are a number of ways you can handle
cache expiration. The simplest is using the `expire_after` param with a value in seconds:
```python
# Expire after 30 seconds
session = CachedSession(expire_after=30)
```

Or a `timedelta`:
```python
from datetime import timedelta

# Expire after 30 days
session = CachedSession(expire_after=timedelta(days=30))
```

You can also set expiration on a per-request basis, which will override any session settings:
```python
# Expire after 6 minutes
session.get('http://httpbin.org/get', expire_after=360)
```

If a per-session expiration is set but you want to temporarily disable it, use `-1`:
```python
# Never expire
session.get('http://httpbin.org/get', expire_after=-1)
```

For better performance, expired responses won't be removed immediately, but will be removed
(or replaced) the next time they are accessed. To manually clear all expired responses:
```python
session.remove_expired_responses()
```
Or, when using patching:
```python
requests_cache.remove_expired_responses()
```

Or, to revalidate the cache with a new expiration:
```python
session.remove_expired_responses(expire_after=360)
```

## More Features & Examples
* You can find a working example at Real Python:
  [Caching External API Requests](https://realpython.com/blog/python/caching-external-api-requests)
* There are some additional examples in the [examples/](https://github.com/reclosedev/requests-cache/tree/master/examples) folder
* See [Advanced Usage](https://requests-cache.readthedocs.io/en/latest/advanced_usage.html) for
  details on customizing cache behavior and other features beyond the basics. 

## Related Projects
If `requests-cache` isn't quite what you need, you can help make it better! See the
[Contributing Guide](https://requests-cache.readthedocs.io/en/latest/contributing.html)
for details.

You can also check out these other python cache projects:

* [CacheControl](https://github.com/ionrock/cachecontrol): An HTTP cache for `requests` that caches
  according to uses HTTP headers and status codes
* [aiohttp-client-cache](https://github.com/JWCook/aiohttp-client-cache): An async HTTP cache for
  `aiohttp`, based on `requests-cache`
* [aiohttp-cache](https://github.com/cr0hn/aiohttp-cache): A server-side async HTTP cache for the
  `aiohttp` web server
* [diskcache](https://github.com/grantjenks/python-diskcache): A general-purpose (not HTTP-specific)
  file-based cache built on SQLite
* [aiocache](https://github.com/aio-libs/aiocache): General-purpose (not HTTP-specific) async cache
  backends
