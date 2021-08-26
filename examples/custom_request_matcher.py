#!/usr/bin/env python
"""
Example of a custom {ref}`request matcher <matching>` that caches a new response if the version of
requests-cache, requests, or urllib3 changes.

This generally isn't needed, since anything that causes a deserialization error will simply result
in a new request being sent and cached. But you might want to include a library version in your cache
key if, for example, you suspect a change in the library does not cause errors but **results in
different response content**.

This uses info from {py:func}`requests.help.info`. You can also preview this info from the command
line to see what else is available:
```bash
python -m requests.help
```
"""
from hashlib import sha256
from unittest.mock import patch

from requests import PreparedRequest
from requests.help import info as get_requests_info

import requests_cache
from requests_cache import CachedSession
from requests_cache.cache_keys import create_key


def create_custom_key(request: PreparedRequest, **kwargs) -> str:
    """Make a custom cache key that includes library versions"""
    # Start with the default key created by requests-cache
    base_key = create_key(request, **kwargs)
    key = sha256()
    key.update(base_key.encode('utf-8'))

    # Add versions of requests-cache, requests, and urllib3
    requests_info = get_requests_info()
    for lib in ['requests', 'urllib3']:
        key.update(requests_info[lib]['version'].encode('utf-8'))
    key.update(requests_cache.__version__.encode('utf-8'))

    return key.hexdigest()


def test_cache_key():
    """Test that the custom cache keys are working as expected"""
    session = CachedSession('key-test', key_fn=create_custom_key)
    session.cache.clear()
    session.get('https://httpbin.org/get')
    response = session.get('https://httpbin.org/get')
    assert response.from_cache is True

    # Simulate a major version change
    new_versions = {
        'requests': {'version': '3.0.0'},
        'urllib3': {'version': '2.0.0'},
    }
    with patch('__main__.get_requests_info', return_value=new_versions):
        # A new request will be sent since the cache key no longer matches
        response = session.get('https://httpbin.org/get')
        assert response.from_cache is False


if __name__ == '__main__':
    test_cache_key()
