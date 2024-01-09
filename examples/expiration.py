#!/usr/bin/env python
"""
An example of setting expiration for individual requests
"""
import time

from requests_cache import CachedSession

# Replace this with any other URL you'd like to test
URL = 'https://httpbin.org/get'


def main():
    session = CachedSession('example_cache', backend='sqlite')
    session.cache.clear()

    # By default, cached responses never expire
    response = session.get(URL)
    assert not response.from_cache
    response = session.get(URL)
    assert response.from_cache
    assert not response.expires

    # We can set default expiration for the session using expire_after
    session = CachedSession('example_cache', backend='sqlite', expire_after=60)
    session.cache.clear()
    response = session.get(URL)
    response = session.get(URL)
    print('Expiration time:', response.expires)

    # This can also be overridden for individual requests
    session.cache.clear()
    response = session.get(URL, expire_after=1)
    response = session.get(URL)
    assert response.from_cache
    print('Expiration time:', response.expires)

    # After 1 second, the cached value will expired
    time.sleep(1.1)
    assert response.is_expired
    response = session.get(URL)
    # The cached response will either be replaced
    # or revalidated (if the site supports conditional requests)
    assert response.revalidated or not response.from_cache


if __name__ == '__main__':
    t = time.perf_counter()
    main()
    print('Elapsed: %.3f seconds' % (time.perf_counter() - t))
