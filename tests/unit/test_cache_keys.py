"""The cache_keys module is mostly covered indirectly via other tests.
This just contains tests for some extra edge cases not covered elsewhere.
"""
import pytest
from requests import PreparedRequest

from requests_cache.cache_keys import (
    create_key,
    normalize_dict,
    remove_ignored_body_params,
    remove_ignored_headers,
)


def test_normalize_dict__skip_body():
    assert normalize_dict(b'some bytes', normalize_data=False) == b'some bytes'


CACHE_KEY = 'ece61ff38c7c76fd951bcd4b7bf36bae24bd9ce7f7eebc43720880596093a10b'


# All of the following variations should produce the same cache key
@pytest.mark.parametrize(
    'url, params',
    [
        ('https://example.com?foo=bar&param=1', None),
        ('https://example.com?foo=bar&param=1', {}),
        ('https://example.com/?foo=bar&param=1', {}),
        ('https://example.com?foo=bar&param=1&', {}),
        ('https://example.com?param=1&foo=bar', {}),
        ('https://example.com?param=1', {'foo': 'bar'}),
        ('https://example.com?foo=bar', {'param': '1'}),
        ('https://example.com', {'foo': 'bar', 'param': '1'}),
        ('https://example.com', {'foo': 'bar', 'param': 1}),
        ('https://example.com?', {'foo': 'bar', 'param': '1'}),
    ],
)
def test_normalize_url_params(url, params):
    request = PreparedRequest()
    request.prepare(
        method='GET',
        url=url,
        params=params,
    )
    assert create_key(request) == CACHE_KEY


def test_remove_ignored_body_params__binary():
    request = PreparedRequest()
    request.method = 'GET'
    request.url = 'https://img.site.com/base/img.jpg'
    request.body = b'some bytes'
    request.headers = {'Content-Type': 'application/octet-stream'}
    assert remove_ignored_body_params(request, ignored_parameters=None) == request.body


def test_remove_ignored_headers__empty():
    request = PreparedRequest()
    request.method = 'GET'
    request.url = 'https://img.site.com/base/img.jpg'
    request.headers = {'foo': 'bar'}
    assert remove_ignored_headers(request, ignored_parameters=None) == request.headers
