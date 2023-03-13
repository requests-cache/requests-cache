from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from requests import PreparedRequest, Request

from requests_cache.cache_keys import create_key
from requests_cache.models import CachedResponse
from requests_cache.policy.actions import EXPIRE_IMMEDIATELY, CacheActions
from requests_cache.policy.settings import CacheSettings
from tests.conftest import ETAG, HTTPDATE_STR, LAST_MODIFIED, MOCKED_URL, get_mock_response

IGNORED_DIRECTIVES = [
    'no-transform',
    'private',
    'proxy-revalidate',
    'public',
    's-maxage=<seconds>',
]
BASIC_REQUEST = Request(method='GET', url='https://site.com/img.jpg', headers={})
EXPIRED_RESPONSE = CachedResponse(expires=datetime.utcnow() - timedelta(1))


@pytest.mark.parametrize(
    'request_expire_after, url_expire_after, expected_expiration',
    [
        (2, 3, 2),
        (None, 3, 3),
        (2, None, 2),
        (None, None, 1),
    ],
)
@patch('requests_cache.policy.actions.get_url_expiration')
def test_init(
    get_url_expiration,
    request_expire_after,
    url_expire_after,
    expected_expiration,
):
    """Test precedence with various combinations or per-request, per-session, per-URL, and
    Cache-Control expiration
    """
    request = PreparedRequest()
    request.url = 'https://img.site.com/base/img.jpg'
    if request_expire_after:
        request.headers = {'Cache-Control': f'max-age={request_expire_after}'}
    get_url_expiration.return_value = url_expire_after

    settings = CacheSettings(cache_control=True, expire_after=1)
    actions = CacheActions.from_request(cache_key='key', request=request, settings=settings)
    assert actions.expire_after == expected_expiration


@pytest.mark.parametrize(
    'headers, expected_expiration',
    [
        ({}, None),
        ({'Expires': HTTPDATE_STR}, None),  # Only valid for response headers
        ({'Cache-Control': 'max-age=60'}, 60),
        ({'Cache-Control': 'public, max-age=60'}, 60),
        ({'Cache-Control': b'public, max-age=60'}, 60),  # requests-oauthlib casts headers to bytes
        ({'Cache-Control': 'max-age=0'}, EXPIRE_IMMEDIATELY),
    ],
)
def test_init_from_headers(headers, expected_expiration):
    """Test with Cache-Control request headers"""
    settings = CacheSettings(cache_control=True)
    request = Request(method='GET', url=MOCKED_URL, headers=headers).prepare()
    actions = CacheActions.from_request('key', request, settings)

    assert actions.cache_key == 'key'
    if expected_expiration != EXPIRE_IMMEDIATELY:
        assert actions.expire_after == expected_expiration
        assert actions.skip_read is False
        assert actions.skip_write is False


def test_init_from_headers__no_store():
    """Test with Cache-Control request headers"""
    settings = CacheSettings(cache_control=True)
    request = Request(method='GET', url=MOCKED_URL, headers={'Cache-Control': 'no-store'}).prepare()
    actions = CacheActions.from_request('key', request, settings)

    assert actions.skip_read is True
    assert actions.skip_write is True


@pytest.mark.parametrize(
    'url, request_expire_after, expected_expiration',
    [
        ('https://img.site_1.com', None, timedelta(hours=12)),
        ('https://img.site_1.com', 60, 60),
        ('https://img.site.com/base/', None, 1),
        ('https://img.site.com/base/img.jpg', None, 1),
        ('http://site_2.com/resource_1', None, timedelta(hours=20)),
        ('ftp://site_2.com/resource_1/index.html', None, timedelta(hours=20)),
        ('http://site_2.com/resource_2/', None, timedelta(days=7)),
        ('http://site_2.com/static/', None, -1),
        ('http://site_2.com/static/img.jpg', None, -1),
        ('http://site_2.com', None, 1),
        ('http://site_2.com', 60, 60),
        ('https://some_other_site.com', None, 1),
        ('https://some_other_site.com', 60, 60),
    ],
)
def test_init_from_settings(url, request_expire_after, expected_expiration):
    """Test with per-session, per-request, and per-URL expiration"""
    settings = CacheSettings(
        expire_after=1,
        urls_expire_after={
            '*.site_1.com': timedelta(hours=12),
            'site_2.com/resource_1': timedelta(hours=20),
            'site_2.com/resource_2': timedelta(days=7),
            'site_2.com/static': -1,
        },
    )
    request = Request(method='GET', url=url)
    if request_expire_after:
        request.headers = {'Cache-Control': f'max-age={request_expire_after}'}

    actions = CacheActions.from_request('key', request.prepare(), settings)
    assert actions.expire_after == expected_expiration


@pytest.mark.parametrize(
    'headers, expire_after, expected_expiration, expected_skip_read',
    [
        ({'Cache-Control': 'max-age=60'}, 1, 60, False),
        ({}, 1, 1, False),
        ({}, 0, 0, False),
        ({'Cache-Control': 'max-age=60'}, 1, 60, False),
        ({'Cache-Control': 'max-age=0'}, 1, 0, False),
        ({'Cache-Control': 'no-store'}, 1, 1, True),
        ({'Cache-Control': 'no-cache'}, 1, 1, True),
    ],
)
def test_init_from_settings_and_headers(
    headers, expire_after, expected_expiration, expected_skip_read
):
    """Test behavior with both cache settings and request headers."""
    request = Request(method='GET', url=MOCKED_URL, headers=headers)
    settings = CacheSettings(expire_after=expire_after)
    actions = CacheActions.from_request('key', request, settings)

    assert actions.expire_after == expected_expiration
    assert actions.skip_read == expected_skip_read


def test_update_from_cached_response__new_request():
    actions = CacheActions.from_request('key', BASIC_REQUEST)
    actions.update_from_cached_response(None)
    assert actions.send_request is True


def test_update_from_cached_response__resend_request():
    actions = CacheActions.from_request('key', BASIC_REQUEST)

    actions.update_from_cached_response(EXPIRED_RESPONSE)
    assert actions.resend_request is True


@pytest.mark.parametrize(
    'response_headers, expected_validation_headers',
    [
        ({}, {}),
        ({'ETag': ETAG}, {'If-None-Match': ETAG}),
        ({'Last-Modified': LAST_MODIFIED}, {'If-Modified-Since': LAST_MODIFIED}),
        (
            {'ETag': ETAG, 'Last-Modified': LAST_MODIFIED},
            {'If-None-Match': ETAG, 'If-Modified-Since': LAST_MODIFIED},
        ),
    ],
)
def test_update_from_cached_response__revalidate(response_headers, expected_validation_headers):
    """Conditional request headers should be added if the cached response is expired"""
    actions = CacheActions.from_request('key', BASIC_REQUEST)
    cached_response = CachedResponse(
        headers=response_headers, expires=datetime.utcnow() - timedelta(1)
    )

    actions.update_from_cached_response(cached_response)
    assert actions.send_request is bool(expected_validation_headers)
    assert actions._validation_headers == expected_validation_headers


@pytest.mark.parametrize(
    'response_headers',
    [
        {'Cache-Control': 'no-cache'},
        {'Cache-Control': 'max-age=0,must-revalidate'},
    ],
)
@pytest.mark.parametrize('cache_control', [True, False])
def test_update_from_cached_response__force_revalidate(cache_control, response_headers):
    """Conditional request headers should be added if requested by response headers, even if the
    response is not expired
    """
    actions = CacheActions.from_request(
        'key',
        request=Request(url='https://img.site.com/base/img.jpg', headers={}),
        settings=CacheSettings(cache_control=cache_control),
    )
    cached_response = CachedResponse(headers={'ETag': ETAG, **response_headers}, expires=None)

    actions.update_from_cached_response(cached_response)

    # cache_control=False overrides revalidation in this case
    if cache_control is False:
        assert actions.send_request is False
        assert not actions._validation_headers
    else:
        assert actions.send_request is True
        assert actions._validation_headers == {'If-None-Match': ETAG}


def test_update_from_cached_response__no_revalidation():
    """Conditional request headers should NOT be added if the cached response is not expired and
    revalidation is otherwise not requested"""
    actions = CacheActions.from_request('key', BASIC_REQUEST)
    cached_response = CachedResponse(
        headers={'ETag': ETAG, 'Last-Modified': LAST_MODIFIED}, expires=None
    )

    actions.update_from_cached_response(cached_response)
    assert actions._validation_headers == {}


def test_update_from_cached_response__504():
    settings = CacheSettings(only_if_cached=True)
    actions = CacheActions.from_request('key', BASIC_REQUEST, settings=settings)
    actions.update_from_cached_response(EXPIRED_RESPONSE)
    assert actions.error_504 is True


def test_update_from_cached_response__stale_if_error():
    settings = CacheSettings(only_if_cached=True, stale_if_error=True)
    actions = CacheActions.from_request('key', BASIC_REQUEST, settings=settings)
    actions.update_from_cached_response(EXPIRED_RESPONSE)
    assert actions.error_504 is False and actions.resend_request is False


def test_update_from_cached_response__stale_while_revalidate():
    settings = CacheSettings(only_if_cached=True, stale_while_revalidate=True)
    actions = CacheActions.from_request('key', BASIC_REQUEST, settings=settings)
    actions.update_from_cached_response(EXPIRED_RESPONSE)
    assert actions.resend_async is True


@pytest.mark.parametrize(
    'vary, cached_headers, new_headers, expected_match',
    [
        ({}, {}, {}, True),
        ({'Vary': 'Accept'}, {'Accept': 'application/json'}, {'Accept': 'application/json'}, True),
        ({'Vary': 'Accept'}, {'Accept': 'application/json'}, {}, False),
        (
            {'Vary': 'Accept'},
            {'Accept': 'application/json'},
            {'Accept': 'application/json', 'Accept-Language': 'en'},
            True,
        ),
        (
            {'Vary': 'Accept-Encoding'},
            {'Accept': 'application/json'},
            {'Accept': 'text/html'},
            True,
        ),
        ({'Vary': 'Accept'}, {'Accept': 'application/json'}, {'Accept': 'text/html'}, False),
        (
            {'Vary': 'Accept-Encoding'},
            {'Accept-Encoding': 'gzip,deflate'},
            {'Accept-Encoding': 'gzip,deflate'},
            True,
        ),
        # Only basic header normalization is done in create_key() (whitespace, case, order)
        (
            {'Vary': 'Accept-Encoding'},
            {'Accept-Encoding': 'gzip,deflate'},
            {'Accept-Encoding': 'dEfLaTe,  GZIP, '},
            True,
        ),
        (
            {'Vary': 'Accept-Encoding'},
            {'Accept-Encoding': 'gzip,deflate'},
            {'Accept-Encoding': 'gzip,br'},
            False,
        ),
        (
            {'Vary': 'Accept, Accept-Encoding'},
            {'Accept': 'application/json', 'Accept-Encoding': 'gzip,deflate'},
            {'Accept': 'application/json', 'Accept-Encoding': 'gzip,deflate'},
            True,
        ),
        (
            {'Vary': 'Accept, Accept-Encoding'},
            {'Accept': 'application/json', 'Accept-Encoding': 'gzip,deflate'},
            {'Accept': 'application/json', 'Accept-Encoding': 'br'},
            False,
        ),
        (
            {'Vary': 'Accept, Accept-Encoding'},
            {'Accept': 'application/json', 'Accept-Encoding': 'gzip,deflate'},
            {'Accept': 'text/html', 'Accept-Encoding': 'gzip,deflate'},
            False,
        ),
        (
            {'Vary': 'Accept, Accept-Encoding'},
            {'Accept': 'application/json', 'Accept-Encoding': 'gzip,deflate'},
            {'Accept-Encoding': 'gzip,deflate'},
            False,
        ),
        ({'Vary': '*'}, {}, {}, False),
        ({'Vary': '*'}, {'Accept': 'application/json'}, {'Accept': 'application/json'}, False),
    ],
)
def test_update_from_cached_response__vary(vary, cached_headers, new_headers, expected_match):
    cached_response = CachedResponse(
        headers=vary,
        request=Request(method='GET', url='https://site.com/img.jpg', headers=cached_headers),
    )
    request = Request(method='GET', url='https://site.com/img.jpg', headers=new_headers)
    actions = CacheActions.from_request('key', request)
    actions.update_from_cached_response(cached_response, create_key=create_key)

    # If the headers don't match wrt. Vary, expect a new request to be sent (cache miss)
    assert actions.send_request is not expected_match


@pytest.mark.parametrize('max_stale, usable', [(5, False), (15, True)])
def test_is_usable__max_stale(max_stale, usable):
    """For a response that expired 10 seconds ago, it may be either accepted or rejected based on
    max-stale
    """
    request = Request(
        url='https://img.site.com/base/img.jpg',
        headers={'Cache-Control': f'max-stale={max_stale}'},
    )
    actions = CacheActions.from_request('key', request)
    cached_response = CachedResponse(expires=datetime.utcnow() - timedelta(seconds=10))
    assert actions.is_usable(cached_response) is usable


@pytest.mark.parametrize('min_fresh, usable', [(5, True), (15, False)])
def test_is_usable__min_fresh(min_fresh, usable):
    """For a response that expires in 10 seconds, it may be either accepted or rejected based on
    min-fresh
    """
    request = Request(
        url='https://img.site.com/base/img.jpg',
        headers={'Cache-Control': f'min-fresh={min_fresh}'},
    )
    actions = CacheActions.from_request('key', request)
    cached_response = CachedResponse(expires=datetime.utcnow() + timedelta(seconds=10))
    assert actions.is_usable(cached_response) is usable


@pytest.mark.parametrize(
    'stale_if_error, error, usable',
    [
        (5, True, False),
        (15, True, True),
        (15, False, False),
    ],
)
def test_is_usable__stale_if_error(stale_if_error, error, usable):
    """For a response that expired 10 seconds ago, if an error occured while refreshing, it may be
    either accepted or rejected based on stale-if-error
    """
    request = Request(
        url='https://img.site.com/base/img.jpg',
        headers={'Cache-Control': f'stale-if-error={stale_if_error}'},
    )
    actions = CacheActions.from_request('key', request)
    cached_response = CachedResponse(expires=datetime.utcnow() - timedelta(seconds=10))
    assert actions.is_usable(cached_response, error=error) is usable


@pytest.mark.parametrize(
    'stale_while_revalidate, usable',
    [
        (5, False),
        (15, True),
    ],
)
def test_is_usable__stale_while_revalidate(stale_while_revalidate, usable):
    """For a response that expired 10 seconds ago, if an error occured while refreshing, it may be
    either accepted or rejected based on stale-while-revalidate
    """
    request = Request(
        url='https://img.site.com/base/img.jpg',
        headers={'Cache-Control': f'stale-while-revalidate={stale_while_revalidate}'},
    )
    actions = CacheActions.from_request('key', request)
    cached_response = CachedResponse(expires=datetime.utcnow() - timedelta(seconds=10))
    assert actions.is_usable(cached_response=cached_response) is usable


@pytest.mark.parametrize(
    'headers, expected_expiration',
    [
        ({}, None),
        ({'Cache-Control': 'no-cache'}, None),  # Forces revalidation, but no effect on expiration
        ({'Cache-Control': 'max-age=0'}, 0),
        ({'Cache-Control': 'max-age=60'}, 60),
        ({'Cache-Control': 'public, max-age=60'}, 60),
        ({'Cache-Control': 'max-age=0'}, 0),
        ({'Cache-Control': 'immutable'}, -1),
        ({'Cache-Control': 'immutable, max-age=60'}, -1),  # Immutable should take precedence
        ({'Expires': HTTPDATE_STR}, HTTPDATE_STR),
        ({'Expires': HTTPDATE_STR, 'Cache-Control': 'max-age=60'}, 60),
    ],
)
def test_update_from_response(headers, expected_expiration):
    """Test with Cache-Control response headers"""
    actions = CacheActions.from_request('key', BASIC_REQUEST, CacheSettings(cache_control=True))
    actions.update_from_response(get_mock_response(headers=headers))

    assert actions.expire_after == expected_expiration
    assert actions.skip_write is (expected_expiration == EXPIRE_IMMEDIATELY)


def test_update_from_response__no_store():
    actions = CacheActions.from_request('key', BASIC_REQUEST, CacheSettings(cache_control=True))
    actions.update_from_response(get_mock_response(headers={'Cache-Control': 'no-store'}))
    assert actions.skip_write is True


def test_update_from_response__ignored():
    actions = CacheActions.from_request('key', BASIC_REQUEST, CacheSettings(cache_control=False))
    actions.update_from_response(get_mock_response(headers={'Cache-Control': 'max-age=5'}))
    assert actions.expire_after is None


@pytest.mark.parametrize('validator_headers', [{'ETag': ETAG}, {'Last-Modified': LAST_MODIFIED}])
@pytest.mark.parametrize('cache_headers', [{'Cache-Control': 'max-age=0'}, {'Expires': '0'}])
@patch('requests_cache.expiration.datetime')
def test_update_from_response__revalidate(mock_datetime, cache_headers, validator_headers):
    """If expiration is 0 and there's a validator, the response should be cached, but with immediate
    expiration
    """
    actions = CacheActions.from_request('key', BASIC_REQUEST, CacheSettings(cache_control=True))
    response = get_mock_response(headers={**cache_headers, **validator_headers})
    actions.update_from_response(response)

    assert actions.expires == mock_datetime.utcnow()
    assert actions.skip_write is False


@pytest.mark.parametrize('directive', IGNORED_DIRECTIVES)
def test_ignored_headers(directive):
    """Ensure that currently unimplemented Cache-Control headers do not affect behavior"""
    request = Request(
        method='GET', url='https://img.site.com/base/img.jpg', headers={'Cache-Control': directive}
    ).prepare()
    settings = CacheSettings(expire_after=1, cache_control=True)
    actions = CacheActions.from_request('key', request, settings)

    assert actions.expire_after == 1
    assert actions.skip_read is False
    assert actions.skip_write is False
