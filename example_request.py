#!/usr/bin/env python
import time

import requests

import requests_cache


requests_cache.install_cache('example_cache', backend='memory')


def main():
    # Normal caching forever
    response = requests.get('https://httpbin.org/get')
    assert not response.from_cache
    response = requests.get('https://httpbin.org/get')
    assert response.from_cache

    # Changing the expires_after time causes a cache invalidation,
    # thus /get is queried again ...
    response = requests.get('https://httpbin.org/get', expire_after=1)
    assert not response.from_cache
    # ... but cached for 1 second
    response = requests.get('https://httpbin.org/get')
    assert response.from_cache
    # After > 1 second, it's cached value is expired
    time.sleep(1.2)
    response = requests.get('https://httpbin.org/get')
    assert not response.from_cache


if __name__ == "__main__":
    t = time.perf_counter()
    main()
    print('Elapsed: %.3f seconds' % (time.perf_counter() - t))
