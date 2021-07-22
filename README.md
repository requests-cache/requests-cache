# Requests-Cache
[![Build](https://github.com/reclosedev/requests-cache/actions/workflows/build.yml/badge.svg)](https://github.com/reclosedev/requests-cache/actions/workflows/build.yml)
[![Coverage](https://coveralls.io/repos/github/reclosedev/requests-cache/badge.svg?branch=master)](https://coveralls.io/github/reclosedev/requests-cache?branch=master)
[![Documentation](https://img.shields.io/readthedocs/requests-cache/stable)](https://requests-cache.readthedocs.io/en/stable/)
[![PyPI](https://img.shields.io/pypi/v/requests-cache?color=blue)](https://pypi.org/project/requests-cache)
[![PyPI - Python Versions](https://img.shields.io/pypi/pyversions/requests-cache)](https://pypi.org/project/requests-cache)
[![PyPI - Format](https://img.shields.io/pypi/format/requests-cache?color=blue)](https://pypi.org/project/requests-cache)
[![Code Shelter](https://www.codeshelter.co/static/badges/badge-flat.svg)](https://www.codeshelter.co/)

## Summary
**requests-cache** is a transparent, persistent HTTP cache for the python [requests](http://python-requests.org)
library. It's a convenient tool to use with web scraping, consuming REST APIs, slow or rate-limited
sites, or any other scenario in which you're making lots of requests that are expensive and/or
likely to be sent more than once.

See full project documentation at: https://requests-cache.readthedocs.io

## Features
* **Ease of use:** Use as a [drop-in replacement](https://requests-cache.readthedocs.io/en/stable/api.html#sessions)
  for `requests.Session`, or [install globally](https://requests-cache.readthedocs.io/en/stable/user_guide.html#patching)
  to add caching to all `requests` functions
* **Customization:** Works out of the box with zero config, but with plenty of options available
  for customizing cache
  [expiration](https://requests-cache.readthedocs.io/en/stable/user_guide.html#cache-expiration)
  and other [behavior](https://requests-cache.readthedocs.io/en/stable/user_guide.html#cache-options)
* **Persistence:** Includes several [storage backends](https://requests-cache.readthedocs.io/en/stable/user_guide.html#cache-backends):
  SQLite, Redis, MongoDB, GridFS, DynamoDB, and filesystem.
* **Compatibility:** Can be used alongside
  [other popular libraries based on requests](https://requests-cache.readthedocs.io/en/stable/advanced_usage.html#library-compatibility)

# Quickstart
First, install with pip:
```bash
pip install requests-cache
```

Next, use [requests_cache.CachedSession](https://requests-cache.readthedocs.io/en/stable/api.html#sessions)
to send and cache requests. To quickly demonstrate how to use it:

**This takes ~1 minute:**
```python
import requests

session = requests.Session()
for i in range(60):
    session.get('http://httpbin.org/delay/1')
```

**This takes ~1 second:**
```python
import requests_cache

session = requests_cache.CachedSession('demo_cache')
for i in range(60):
    session.get('http://httpbin.org/delay/1')
```

The URL in this example adds a delay of 1 second, simulating a slow or rate-limited website.
With caching, the response will be fetched once, saved to `demo_cache.sqlite`, and subsequent
requests will return the cached response near-instantly.

If you don't want to manage a session object, requests-cache can also be installed globally:
```python
requests_cache.install_cache('demo_cache')
requests.get('http://httpbin.org/delay/1')
```

## Next Steps
To find out more about what you can do with requests-cache, see:

* The
  [User Guide](https://requests-cache.readthedocs.io/en/stable/user_guide.html) and
  [Advanced Usage](https://requests-cache.readthedocs.io/en/stable/advanced_usage.html) sections
* A working example at Real Python:
  [Caching External API Requests](https://realpython.com/blog/python/caching-external-api-requests)
* More examples in the
  [examples/](https://github.com/reclosedev/requests-cache/tree/master/examples) folder
