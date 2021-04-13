#!/usr/bin/env python
"""
Example of converting data cached in older versions of requests-cache (<=0.5.2)
into the current format
"""
from requests import Response
from requests_cache import CachedResponse, CachedSession
import requests_cache.backends.base


class _Store:
    pass


# Add placeholder object used by pickle to deserialize old responses
requests_cache.backends.base._Store = _Store
requests_cache.backends.base._RawStore = _Store


def convert_old_response(cached_response, timestamp):
    temp_response = Response()
    for field in Response.__attrs__:
        setattr(temp_response, field, getattr(cached_response, field, None))

    new_response = CachedResponse(temp_response)
    new_response.created_at = timestamp
    return new_response


def convert_cache(*args, **kwargs):
    session = CachedSession(*args, **kwargs)
    print(f'Checking {len(session.cache.responses)} cached responses')

    with session.cache.responses.bulk_commit():
        for key, response in session.cache.responses.items():
            if isinstance(response, tuple):
                print(f'Converting response {key}')
                session.cache.responses[key] = convert_old_response(*response)

    print('Conversion complete')


# Example: convert a cache named 'demo_cache.sqlite' in the current directory
if __name__ == '__main__':
    convert_cache('demo_cache', backend='sqlite')
