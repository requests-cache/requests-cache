#!/usr/bin/env python
# fmt: off
"""
An example of {ref}`url-patterns`
"""
from datetime import timedelta

from requests_cache import CachedSession

default_expire_after = 60 * 60               # By default, cached responses expire in an hour
urls_expire_after = {
    'httpbin.org/image': timedelta(days=7),  # Requests for this base URL will expire in a week
    '*.fillmurray.com': -1,                  # Requests matching this pattern will never expire
    '*.placeholder.com/*': 0,                # Requests matching this pattern will not be cached
}
urls = [
    'https://httpbin.org/get',               # Will expire in an hour
    'https://httpbin.org/image/jpeg',        # Will expire in a week
    'http://www.fillmurray.com/460/300',     # Will never expire
    'https://via.placeholder.com/350x150',   # Will not be cached
]


def main():
    session = CachedSession(
        cache_name='example_cache',
        expire_after=default_expire_after,
        urls_expire_after=urls_expire_after,
    )
    return [session.get(url) for url in urls]


def _expires_str(response):
    if not response.from_cache:
        return 'N/A'
    elif response.expires is None:
        return 'Never'
    else:
        return response.expires.isoformat()


if __name__ == "__main__":
    original_responses = main()
    cached_responses = main()
    for response in cached_responses:
        print(
            f'{response.url:40} From cache: {response.from_cache:}'
            f'\tExpires: {_expires_str(response)}'
        )
