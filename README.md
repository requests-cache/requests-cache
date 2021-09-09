# Requests-Cache
[![Build](https://github.com/reclosedev/requests-cache/actions/workflows/build.yml/badge.svg)](https://github.com/reclosedev/requests-cache/actions/workflows/build.yml)
[![Documentation](https://img.shields.io/readthedocs/requests-cache/stable)](https://requests-cache.readthedocs.io/en/stable/)[![Coverage](https://coveralls.io/repos/github/reclosedev/requests-cache/badge.svg?branch=master)](https://coveralls.io/github/reclosedev/requests-cache?branch=master)
[![Code Shelter](https://www.codeshelter.co/static/badges/badge-flat.svg)](https://www.codeshelter.co/)

[![PyPI](https://img.shields.io/pypi/v/requests-cache?color=blue)](https://pypi.org/project/requests-cache)
[![Conda](https://img.shields.io/conda/vn/conda-forge/requests-cache?color=blue)](https://anaconda.org/conda-forge/requests-cache)
[![PyPI - Python Versions](https://img.shields.io/pypi/pyversions/requests-cache)](https://pypi.org/project/requests-cache)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/requests-cache?color=blue)](https://pypi.org/project/requests-cache)

## Summary
**requests-cache** is a transparent, persistent cache that provides an easy way to get better
performance with the python [requests](http://python-requests.org) library.

<!-- RTD-IGNORE -->
Complete project documentation can be found at [requests-cache.readthedocs.io](https://requests-cache.readthedocs.io).
<!-- END-RTD-IGNORE -->

## Features
* 🍰 **Ease of use:** Keep using the `requests` library you're already familiar with. Add caching
  with a [drop-in replacement](https://requests-cache.readthedocs.io/en/stable/user_guide/general.html#sessions)
  for `requests.Session`, or
  [install globally](https://requests-cache.readthedocs.io/en/stable/user_guide/general.html#patching)
  to add caching to all `requests` functions.
* 🚀 **Performance:** Get sub-millisecond response times for cached responses. When they expire, you
  still save time with
  [conditional requests](https://requests-cache.readthedocs.io/en/stable/user_guide/headers.html#conditional-requests).
* 💾 **Persistence:** Works with several
  [storage backends](https://requests-cache.readthedocs.io/en/stable/user_guide/backends.html)
  including SQLite, Redis, MongoDB, and DynamoDB; or save responses as plain JSON files, YAML,
  and more
* ⚙️ **Customization:** Works out of the box with zero config, but with a robust set of features for
  configuring and extending the library to suit your needs
* 🕗 **Expiration:** Keep your cache fresh using
  [Cache-Control](https://requests-cache.readthedocs.io/en/stable/user_guide/headers.html#cache-control),
  eagerly cache everything for long-term storage, use
  [URL patterns](https://requests-cache.readthedocs.io/en/stable/user_guide/expiration.html#expiration-with-url-patterns)
  for selective caching, or any combination of strategies
* ✔️ **Compatibility:** Can be combined with other popular
  [libraries based on requests](https://requests-cache.readthedocs.io/en/stable/user_guide/compatibility.html)

## Quickstart
First, install with pip:
```bash
pip install requests-cache
```

Then, use [requests_cache.CachedSession](https://requests-cache.readthedocs.io/en/stable/session.html)
to make your requests. It behaves like a normal
[requests.Session](https://docs.python-requests.org/en/master/user/advanced/#session-objects),
but with caching behavior.

To illustrate, we'll call an endpoint that adds a delay of 1 second, simulating a slow or
rate-limited website.

**This takes 1 minute:**
```python
import requests

session = requests.Session()
for i in range(60):
    session.get('http://httpbin.org/delay/1')
```

**This takes 1 second:**
```python
import requests_cache

session = requests_cache.CachedSession('demo_cache')
for i in range(60):
    session.get('http://httpbin.org/delay/1')
```

With caching, the response will be fetched once, saved to `demo_cache.sqlite`, and subsequent
requests will return the cached response near-instantly.

**Patching:**

If you don't want to manage a session object, or just want to quickly test it out in your
application without modifying any code, requests-cache can also be installed globally, and all
requests will be transparently cached:
```python
import requests
import requests_cache

requests_cache.install_cache('demo_cache')
requests.get('http://httpbin.org/delay/1')
```

**Configuration:**

A quick example of some of the options available:
```python
# fmt: off
from datetime import timedelta
from requests_cache import CachedSession

session = CachedSession(
    'demo_cache',
    use_cache_dir=True,                # Save files in the default user cache dir
    cache_control=True,                # Use Cache-Control headers for expiration, if available
    expire_after=timedelta(days=1),    # Otherwise expire responses after one day
    allowable_methods=['GET', 'POST'], # Cache POST requests to avoid sending the same data twice
    allowable_codes=[200, 400],        # Cache 400 responses as a solemn reminder of your failures
    ignored_parameters=['api_key'],    # Don't match this param or save it in the cache
    match_headers=True,                # Match all request headers
    stale_if_error=True,               # In case of request errors, use stale cache data if possible
)
```

<!-- RTD-IGNORE -->
## Next Steps
To find out more about what you can do with requests-cache, see:

* [User Guide](https://requests-cache.readthedocs.io/en/stable/user_guide.html)
* [API Reference](https://requests-cache.readthedocs.io/en/stable/reference.html)
* [Project Info](https://requests-cache.readthedocs.io/en/stable/project_info.html)
* A working example at Real Python:
  [Caching External API Requests](https://realpython.com/blog/python/caching-external-api-requests)
* More examples in the
  [examples/](https://github.com/reclosedev/requests-cache/tree/master/examples) folder
<!-- END-RTD-IGNORE -->
