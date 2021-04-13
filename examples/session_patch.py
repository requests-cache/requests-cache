#!/usr/bin/env python
# flake8: noqa: F841
"""
The same as ``basic_usage.py``, but using global session patching
"""
import time

import requests
import requests_cache

# After installation, all requests functions and Session methods will be cached
requests_cache.install_cache('example_cache', backend='sqlite')


def main():
    # The real request will only be made once; afterward, the cached response is used
    for i in range(5):
        response = requests.get('http://httpbin.org/get')

    # This is more obvious when calling a slow endpoint
    for i in range(5):
        response = requests.get('http://httpbin.org/delay/2')

    # Caching can be disabled if we want to get a fresh page and not cache it
    with requests_cache.disabled():
        print(requests.get('http://httpbin.org/ip').text)

    # Get some debugging info about the cache
    print(requests_cache.get_cache())
    print('Cached URLS:', requests_cache.get_cache().urls)

    # Uninstall to remove caching from all requests functions
    requests_cache.uninstall_cache()


if __name__ == "__main__":
    t = time.time()
    main()
    print('Elapsed: %.3f seconds' % (time.time() - t))
