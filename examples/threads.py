#!/usr/bin/env python
"""
An example of making multi-threaded cached requests, adapted from the python docs for
{py:class}`~concurrent.futures.ThreadPoolExecutor`.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter as time

from requests_cache import CachedSession

URLS = [
    'https://en.wikipedia.org/wiki/Python_(programming_language)',
    'https://en.wikipedia.org/wiki/Requests_(software)',
    'https://en.wikipedia.org/wiki/Cache_(computing)',
    'https://en.wikipedia.org/wiki/SQLite',
    'https://en.wikipedia.org/wiki/Redis',
    'https://en.wikipedia.org/wiki/MongoDB',
]


def send_requests():
    session = CachedSession('example_cache')
    start = time()

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {executor.submit(session.get, url): url for url in URLS}

        for future in as_completed(future_to_url):
            url = future_to_url[future]
            response = future.result()
            from_cache = 'hit' if response.from_cache else 'miss'
            print(f'{url} is {len(response.content)} bytes (cache {from_cache})')

    print(f'Elapsed: {time() - start:.3f} seconds')


if __name__ == '__main__':
    send_requests()
    send_requests()
