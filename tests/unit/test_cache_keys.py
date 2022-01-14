"""The cache_keys module is mostly covered indirectly via other tests.
This just contains tests for some extra edge cases not covered elsewhere.
"""
import pytest
from requests import PreparedRequest, Request

from requests_cache.cache_keys import create_key, normalize_request

CACHE_KEY = 'e8cb526891875e37'


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
def test_create_key__normalize_url_params(url, params):
    """All of the above variations should produce the same cache key"""
    request = Request(
        method='GET',
        url=url,
        params=params,
    )
    assert create_key(request) == CACHE_KEY


def test_create_key__normalize_key_only_params():
    request_1 = Request(method='GET', url='https://img.site.com/base/img.jpg?param_1')
    request_2 = Request(method='GET', url='https://img.site.com/base/img.jpg?param_2')
    assert create_key(request_1) != create_key(request_2)


def test_normalize_request__json_body():
    request = Request(
        method='GET',
        url='https://img.site.com/base/img.jpg',
        data=b'{"param_1": "value_1", "param_2": "value_2"}',
        headers={'Content-Type': 'application/json'},
    )
    assert (
        normalize_request(request, ignored_parameters=['param_2']).body == b'{"param_1": "value_1"}'
    )


def test_normalize_request__invalid_json_body():
    request = Request(
        method='GET',
        url='https://img.site.com/base/img.jpg',
        data=b'invalid JSON!',
        headers={'Content-Type': 'application/json'},
    )
    assert normalize_request(request, ignored_parameters=['param_2']).body == b'invalid JSON!'


def test_normalize_request__binary_body():
    request = Request(
        method='GET',
        url='https://img.site.com/base/img.jpg',
        data=b'some bytes',
        headers={'Content-Type': 'application/octet-stream'},
    )
    assert normalize_request(request, ignored_parameters=['param']).body == request.data


def test_remove_ignored_headers__empty():
    request = PreparedRequest()
    request.prepare(
        method='GET',
        url='https://img.site.com/base/img.jpg',
        headers={'foo': 'bar'},
    )
    assert normalize_request(request, ignored_parameters=None).headers == request.headers
