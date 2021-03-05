# requests-cache
Requests-cache is a transparent persistent cache for the [requests](http://python-requests.org) library (version 2+).

[![Build](https://github.com/reclosedev/requests-cache/actions/workflows/build.yml/badge.svg)](https://github.com/reclosedev/requests-cache/actions/workflows/build.yml)
[![Coverage](https://coveralls.io/repos/github/reclosedev/requests-cache/badge.svg?branch=master)](https://coveralls.io/github/reclosedev/requests-cache?branch=master)
[![Documentation](https://img.shields.io/readthedocs/requests-cache/latest)](https://requests-cache.readthedocs.io/en/latest/)
[![PyPI](https://img.shields.io/pypi/v/requests-cache?color=blue)](https://pypi.org/project/requests-cache)
[![PyPI - Python Versions](https://img.shields.io/pypi/pyversions/requests-cache)](https://pypi.org/project/requests-cache)
[![PyPI - Format](https://img.shields.io/pypi/format/requests-cache?color=blue)](https://pypi.org/project/requests-cache)
[![Code Shelter](https://www.codeshelter.co/static/badges/badge-flat.svg)](https://www.codeshelter.co/)

## Installation
Install with pip:
```
pip install requests-cache
```

## Usage example
```python
import requests_cache

requests_cache.install_cache('demo_cache')
```

And all responses with headers and cookies will be transparently cached to `demo_cache.sqlite`.
For example, following the code will take only 1-2 seconds instead of 10, and will run instantly on next launch:

```python
import requests

for i in range(10):
    requests.get('http://httpbin.org/delay/1')
```

It can be useful when you are creating some simple data scraper with constantly
changing parsing logic or data format, and don't want to redownload pages or
write complex error handling and persistence.

For more complex workflows, it is possible to cache different requests with different expiration times, or disable caching for a specific request completely:


For more complex workflows, it is possible to cache different requests with different expiry times, or disable caching for a specific request completely:

```python
import time
import requests
import requests_cache

requests_cache.install_cache('demo_cache')

# Hits the URL only 2 times
for i in range(10):
    requests.get('http://httpbin.org/delay/1', expire_after=1)
    time.sleep(0.2)

# Disable caching (and invalidate cache)
requests.get('http://httpbin.org/delay/1', expire_after=-1)  # always from URL
requests.get('http://httpbin.org/delay/1')  # always from URL
```


## Related Projects
If `requests-cache` isn't quite what you need, you can help make it better! See the
[Contributing Guide](https://github.com/reclosedev/requests-cache/blob/master/CONTRIBUTING.md)
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

## Links
- **Documentation** at [readthedocs](https://requests-cache.readthedocs.io)
- **Source code and issue tracking** at [GitHub](https://github.com/reclosedev/requests-cache)
- **Working example** at [Real Python](https://realpython.com/blog/python/caching-external-api-requests)
