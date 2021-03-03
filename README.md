# requests-cache
Requests-cache is a transparent persistent cache for the [requests](http://python-requests.org) library (version 2+).

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

## Links
- **Documentation** at [readthedocs](https://requests-cache.readthedocs.io)
- **Source code and issue tracking** at [GitHub](https://github.com/reclosedev/requests-cache)
- **Working example** at [Real Python](https://realpython.com/blog/python/caching-external-api-requests)
