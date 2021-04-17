#!/usr/bin/env python
# flake8: noqa: F841
"""
A simple example using requests-cache with httpbin
"""
import time

from requests_cache import CachedSession


def main():
    session = CachedSession('example_cache', backend='sqlite')

    # The real request will only be made once; afterward, the cached response is used
    for i in range(5):
        response = session.get('http://httpbin.org/get')

    # This is more obvious when calling a slow endpoint
    for i in range(5):
        response = session.get('http://httpbin.org/delay/2')

    # Caching can be disabled if we want to get a fresh page and not cache it
    with session.cache_disabled():
        print(session.get('http://httpbin.org/ip').text)

    # Get some debugging info about the cache
    print(session.cache)
    print('Cached URLS:', session.cache.urls)


if __name__ == "__main__":
    t = time.time()
    main()
    print('Elapsed: %.3f seconds' % (time.time() - t))
