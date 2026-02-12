"""The cache_keys module is mostly covered indirectly via other tests.
This just contains tests for some extra edge cases not covered elsewhere.
"""

from io import BytesIO
import json

import pytest
from requests import Request, Response
from urllib3 import HTTPResponse
from unittest.mock import patch

from requests_cache.cache_keys import (
    MAX_NORM_BODY_SIZE,
    create_key,
    filter_sort_dict,
    normalize_headers,
    normalize_request,
    redact_response,
)

CACHE_KEY = 'e25f7e6326966e82'


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
        ('https://example.com', {'param': '1', 'foo': 'bar'}),
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

    request_1 = Request(method='GET', url='https://img.site.com/base/img.jpg?k=v&param_1')
    request_2 = Request(method='GET', url='https://img.site.com/base/img.jpg?param_1&k=v')
    assert create_key(request_1) == create_key(request_2)


def test_create_key__normalize_duplicate_params():
    request_1 = Request(method='GET', url='https://img.site.com/base/img.jpg?param_1=a&param_1=b')
    request_2 = Request(method='GET', url='https://img.site.com/base/img.jpg?param_1=a')
    request_3 = Request(method='GET', url='https://img.site.com/base/img.jpg?param_1=b')
    assert create_key(request_1) != create_key(request_2) != create_key(request_3)

    request_1 = Request(
        method='GET', url='https://img.site.com/base/img.jpg?param_1=a&param_1=b&k=v'
    )
    request_2 = Request(
        method='GET',
        url='https://img.site.com/base/img.jpg?param_1=b&param_1=a',
        params={'k': 'v'},
    )
    assert create_key(request_1) == create_key(request_2)


def test_create_key__fips_hash_fallback():
    """Test that if blake2b fails due to FIPS mode, it creates a valid key using a different
    hash function. Fallback on TypeError and ValueError - both are possible in FIPS mode.
    """
    request = Request(method='GET', url='https://example.com')
    key_1 = create_key(request)

    with patch('requests_cache.cache_keys.blake2b') as mock_blake2b:
        mock_blake2b.side_effect = TypeError
        key_2 = create_key(request)
        mock_blake2b.side_effect = ValueError
        key_3 = create_key(request)

    assert key_1 != key_2
    assert key_2 == key_3  # Fallback to the same algorithm


def test_redact_response__escaped_params():
    """Test that redact_response() handles urlescaped request parameters"""
    url = 'https://img.site.com/base/img.jpg?where=code%3D123'
    request = Request(method='GET', url=url).prepare()
    response = Response()
    response.url = url
    response.request = request
    response.raw = HTTPResponse(request_url=url)
    redacted_response = redact_response(response, [])
    assert redacted_response.url == 'https://img.site.com/base/img.jpg?where=code%3D123'
    assert redacted_response.request.url == 'https://img.site.com/base/img.jpg?where=code%3D123'
    assert redacted_response.request.path_url == '/base/img.jpg?where=code%3D123'
    assert (
        redacted_response.raw._request_url == 'https://img.site.com/base/img.jpg?where=code%3D123'
    )
    if hasattr(redacted_response.raw, 'url'):
        assert redacted_response.raw.url == 'https://img.site.com/base/img.jpg?where=code%3D123'


@pytest.mark.parametrize(
    'content_type',
    [
        'application/json',
        'application/json; charset=utf-8',
        'application/vnd.api+json; charset=utf-8',
        'application/any_string+json',
    ],
)
@pytest.mark.parametrize(
    'data',
    [
        b'{"param_1": "value_1", "param_2": "value_2"}',
        b'["param_3", "param_2", "param_1"',
    ],
)
def test_normalize_request__json_body(data, content_type):
    request = Request(
        method='GET',
        url='https://img.site.com/base/img.jpg',
        data=b'{"param_1": "value_1", "param_2": "value_2"}',
        headers={'Content-Type': content_type},
    )
    norm_request = normalize_request(request, ignored_parameters=['param_2'])
    assert norm_request.body == b'{"param_1": "value_1", "param_2": "REDACTED"}'


def test_normalize_request__json_body_list_filtered():
    request = Request(
        method='GET',
        url='https://img.site.com/base/img.jpg',
        data=b'["param_3", "param_2", "param_1"]',
        headers={'Content-Type': 'application/json'},
    )
    norm_request = normalize_request(request, ignored_parameters=['param_2', 'param_1'])
    assert norm_request.body == b'["param_3"]'


def test_normalize_request__json_body_invalid():
    request = Request(
        method='GET',
        url='https://img.site.com/base/img.jpg',
        data=b'invalid JSON!',
        headers={'Content-Type': 'application/json'},
    )
    assert normalize_request(request, ignored_parameters=['param_2']).body == b'invalid JSON!'


def test_normalize_request__json_body_empty():
    request = Request(
        method='GET',
        url='https://img.site.com/base/img.jpg',
        data=b'{}',
        headers={'Content-Type': 'application/json'},
    )
    assert normalize_request(request, ignored_parameters=['param_2']).body == b'{}'


@pytest.mark.parametrize(
    'content_type',
    ['application/octet-stream', None],
)
def test_normalize_request__binary_body(content_type):
    request = Request(
        method='GET',
        url='https://img.site.com/base/img.jpg',
        data=b'some bytes',
        headers={'Content-Type': content_type},
    )
    assert normalize_request(request, ignored_parameters=['param']).body == request.data


def test_normalize_request__oversized_body():
    body = {'param': '1', 'content': '0' * MAX_NORM_BODY_SIZE}
    encoded_body = json.dumps(body).encode('utf-8')

    request = Request(
        method='GET',
        url='https://img.site.com/base/img.jpg',
        json=body,
        headers={'Content-Type': 'application/octet-stream'},
    )
    assert normalize_request(request, ignored_parameters=['param']).body == encoded_body


def test_normalize_request__file_like_body():
    original_body = BytesIO(b'some bytes')
    request = Request(
        method='GET',
        url='https://img.site.com/base/img.jpg',
        data=original_body,
        headers={'Content-Type': 'application/json'},
    )
    assert normalize_request(request).body == b'some bytes'
    assert original_body.read() == b'some bytes'


def test_normalize_request__file_like_reset_fails():
    """Test a request body with a file-like class that doesn't support seek()"""

    class CustomBytesIO:
        def __init__(self, content):
            self.content = content

        def __len__(self):
            return len(self.content)

        def read(self):
            return self.content

    original_body = CustomBytesIO(b'some bytes')
    request = Request(
        method='GET',
        url='https://img.site.com/base/img.jpg',
        data=original_body,
        headers={'Content-Type': 'application/json'},
    )
    assert normalize_request(request).body == b'some bytes'
    assert original_body.read() == b'some bytes'


def test_normalize_headers__single_header_value_as_bytes():
    headers = {'Accept': b'gzip'}
    norm_headers = normalize_headers(headers)
    assert norm_headers == {'Accept': 'gzip'}


def test_normalize_headers__multiple_header_values_as_bytes():
    headers = {'Accept': b'gzip,  deflate,Venmo,  PayPal, '}
    norm_headers = normalize_headers(headers)
    assert norm_headers == {'Accept': 'deflate, gzip, paypal, venmo'}


def test_normalize_headers__single_header_value_as_string():
    headers = {'Accept': 'gzip'}
    norm_headers = normalize_headers(headers)
    assert norm_headers == {'Accept': 'gzip'}


def test_normalize_headers__multiple_header_values_as_string():
    headers = {'Accept': 'gzip,  deflate,Venmo,  PayPal, '}
    norm_headers = normalize_headers(headers)
    assert norm_headers == {'Accept': 'deflate, gzip, paypal, venmo'}


def test_remove_ignored_headers__empty():
    request = Request(
        method='GET',
        url='https://img.site.com/base/img.jpg',
        headers={'foo': 'bar'},
    )
    assert normalize_request(request.prepare(), ignored_parameters=None).headers == request.headers


def test_create_key__hashed_parameters__same_value():
    """Requests with the same hashed parameter value should get the same cache key"""
    request_1 = Request(
        method='GET',
        url='https://example.com/api/me',
        headers={'Authorization': 'Bearer same-token'},
    )
    request_2 = Request(
        method='GET',
        url='https://example.com/api/me',
        headers={'Authorization': 'Bearer same-token'},
    )
    key_1 = create_key(request_1, hashed_parameters=['Authorization'])
    key_2 = create_key(request_2, hashed_parameters=['Authorization'])
    assert key_1 == key_2


@pytest.mark.parametrize(
    'kwargs, expect_different',
    [
        pytest.param(
            {'hashed_parameters': ['Authorization']},
            True,
            id='hashed',
        ),
        pytest.param(
            {'hashed_parameters': ['Authorization'], 'ignored_parameters': ['Authorization']},
            True,
            id='hashed_precedence_over_ignored',
        ),
        pytest.param(
            {'hashed_parameters': ['Authorization'], 'match_headers': ['Accept-Language']},
            True,
            id='hashed_with_explicit_match_headers',
        ),
        pytest.param(
            {'ignored_parameters': ['Authorization']},
            False,
            id='ignored_only',
        ),
    ],
)
def test_create_key__hashed_parameters(kwargs, expect_different):
    """With different Authorization values, cache keys should differ when hashed_parameters
    is set, and match when only ignored_parameters is set (control case)."""
    request_1 = Request(
        method='GET',
        url='https://example.com/api/me',
        headers={'Authorization': 'Bearer token-1', 'Accept-Language': 'en'},
    )
    request_2 = Request(
        method='GET',
        url='https://example.com/api/me',
        headers={'Authorization': 'Bearer token-2', 'Accept-Language': 'en'},
    )
    key_1 = create_key(request_1, **kwargs)
    key_2 = create_key(request_2, **kwargs)
    assert (key_1 != key_2) == expect_different


@pytest.mark.parametrize(
    'ignored_parameters',
    [
        pytest.param(None, id='hashed_only'),
        pytest.param(['Authorization'], id='hashed_over_ignored'),
    ],
)
def test_filter_sort_dict__hashed_parameters(ignored_parameters):
    """filter_sort_dict should hash values for hashed_parameters, taking precedence
    over ignored_parameters when both are specified."""
    from hashlib import sha256

    data = {'Authorization': 'Bearer my-token', 'Accept': 'application/json'}
    result = filter_sort_dict(
        data, ignored_parameters=ignored_parameters, hashed_parameters=['Authorization']
    )
    assert result['Authorization'] == sha256(b'Bearer my-token').hexdigest()
    assert result['Accept'] == 'application/json'


def test_redact_response__hashed_parameters():
    """Both hashed_parameters and ignored_parameters should be redacted in stored responses"""
    url = 'https://example.com/api/me'
    request = Request(
        method='GET',
        url=url,
        headers={
            'Authorization': 'Bearer secret-token',
            'X-API-KEY': 'my-api-key',
        },
    ).prepare()
    response = Response()
    response.url = url
    response.request = request
    response.headers = {}
    response.raw = HTTPResponse(request_url=url)

    redacted = redact_response(
        response,
        ignored_parameters=['X-API-KEY'],
        hashed_parameters=['Authorization'],
    )
    assert redacted.request.headers['Authorization'] == 'REDACTED'
    assert redacted.request.headers['X-API-KEY'] == 'REDACTED'
