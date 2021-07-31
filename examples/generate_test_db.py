#!/usr/bin/env python
"""An example of generating a test database with a large number of semi-randomized responses.
This is useful, for example, for reproducing issues that only occur with large caches.
"""
import logging
from datetime import datetime, timedelta
from os import urandom
from os.path import getsize
from random import random
from time import perf_counter as time

import requests
from rich.progress import Progress

from requests_cache import ALL_METHODS, CachedSession, CachedResponse
from requests_cache.models.response import format_file_size
from tests.conftest import HTTPBIN_FORMATS, HTTPBIN_METHODS


BASE_RESPONSE = requests.get('https://httpbin.org/get')
CACHE_NAME = 'rubbish_bin.sqlite'
HTTPBIN_EXTRA_ENDPOINTS = [
    'anything',
    'bytes/1024' 'cookies',
    'ip',
    'redirect/5',
    'stream-bytes/1024',
]
MAX_EXPIRE_AFTER = 30
MAX_RESPONSE_SIZE = 10000
N_RESPONSES = 100000
N_INVALID_RESPONSES = 10

logging.basicConfig(level='INFO')
logger = logging.getLogger('requests_cache')


class InvalidResponse(CachedResponse):
    """Response that will raise an exception when deserialized"""

    def __setstate__(self, d):
        raise ValueError


def populate_cache(progress, task):
    session = CachedSession(CACHE_NAME, backend='sqlite', allowable_methods=ALL_METHODS)
    n_previous_responses = len(session.cache.responses)

    # Cache a variety of different response formats, which may result in different behavior
    urls = [
        ('GET', 'https://httpbin.org/{endpoint}')
        for endpoint in HTTPBIN_FORMATS + HTTPBIN_EXTRA_ENDPOINTS
    ]
    urls += [(method, 'https://httpbin.org/{method.lower()}') for method in HTTPBIN_METHODS]
    for method, url in urls:
        session.request(method, url)
        progress.update(task, advance=1)

    # Cache a large number of responses with randomized response content, which will expire at random times
    with session.cache.responses.bulk_commit():
        for i in range(N_RESPONSES):
            new_response = get_randomized_response(i + n_previous_responses)
            expires = datetime.now() + timedelta(seconds=random() * MAX_EXPIRE_AFTER)
            session.cache.save_response(new_response, expires=expires)
            progress.update(task, advance=1)

    # Add some invalid responses
    with session.cache.responses.bulk_commit():
        for i in range(N_INVALID_RESPONSES):
            new_response = InvalidResponse.from_response(BASE_RESPONSE)
            new_response.request.url += f'/invalid_response_{i}'
            key = session.cache.create_key(new_response.request)
            session.cache.responses[key] = new_response
            progress.update(task, advance=1)


def get_randomized_response(i=0):
    """Get a response with randomized content"""
    new_response = CachedResponse.from_response(BASE_RESPONSE)
    n_bytes = int(random() * MAX_RESPONSE_SIZE)
    new_response._content = urandom(n_bytes)
    new_response.request.url += f'/response_{i}'
    return new_response


def remove_expired_responses(expire_after=None):
    logger.setLevel('DEBUG')
    session = CachedSession(CACHE_NAME)
    total_responses = len(session.cache.responses)

    start = time()
    session.remove_expired_responses(expire_after=expire_after)
    elapsed = time() - start
    n_removed = total_responses - len(session.cache.responses)
    logger.info(
        f'Removed {n_removed} expired/invalid responses in {elapsed:.2f} seconds '
        f'(avg {(elapsed / n_removed) * 1000:.2f}ms per response)'
    )


def main():
    total_responses = len(HTTPBIN_FORMATS + HTTPBIN_EXTRA_ENDPOINTS + HTTPBIN_METHODS)
    total_responses += N_RESPONSES + N_INVALID_RESPONSES

    with Progress() as progress:
        task = progress.add_task('[cyan]Generating responses...', total=total_responses)
        populate_cache(progress, task)

    actual_total_responses = len(CachedSession(CACHE_NAME).cache.responses)
    cache_file_size = format_file_size(getsize(CACHE_NAME))
    logger.info(f'Generated cache with {actual_total_responses} responses ({cache_file_size})')


if __name__ == '__main__':
    main()

    # Remove some responses (with randomized expiration)
    # remove_expired_responses()

    # Expire and remove all responses
    # remove_expired_responses(expire_after=1)
