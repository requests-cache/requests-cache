#!/usr/bin/env python
"""An example of benchmarking cache write speeds with semi-randomized response content"""
from os import urandom
from random import random
from time import perf_counter as time

import requests

from requests_cache import CachedResponse, CachedSession

BASE_RESPONSE = requests.get('https://httpbin.org/get')
CACHE_NAME = 'rubbish_bin.sqlite'
ITERATIONS = 5000
MAX_RESPONSE_SIZE = 1024 * 6


def test_write_speed(session):
    start = time()
    for i in range(ITERATIONS):
        new_response = get_randomized_response(i)
        session.cache.save_response(new_response)

    elapsed = time() - start
    avg = (elapsed / ITERATIONS) * 1000
    print(f'Elapsed: {elapsed:.3f} (avg {avg:.3f}ms per write)')


def get_randomized_response(i=0):
    """Get a response with randomized content"""
    new_response = CachedResponse.from_response(BASE_RESPONSE)
    n_bytes = int(random() * MAX_RESPONSE_SIZE)
    new_response._content = urandom(n_bytes)
    new_response.request.url += f'/response_{i}'
    return new_response


if __name__ == '__main__':
    session = CachedSession(CACHE_NAME, backend='sqlite')
    test_write_speed(session)
