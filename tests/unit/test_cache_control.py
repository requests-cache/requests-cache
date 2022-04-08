from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from requests import PreparedRequest

from requests_cache.cache_control import DO_NOT_CACHE, CacheActions
from requests_cache.models import CachedResponse
from requests_cache.settings import CacheSettings, RequestSettings
from tests.conftest import ETAG, HTTPDATE_STR, LAST_MODIFIED, get_mock_response

IGNORED_DIRECTIVES = [
    'no-transform',
    'private',
    'proxy-revalidate',
    'public',
    's-maxage=<seconds>',
]


@pytest.mark.parametrize(
    'request_expire_after, url_expire_after, expected_expiration',
    [
        (2, 3, 2),
        (None, 3, 3),
        (2, None, 2),
        (None, None, 1),
    ],
)
@patch('requests_cache.cache_control.get_url_expiration')
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
    settings = RequestSettings.merge(settings, expire_after=request_expire_after)
    actions = CacheActions.from_request(
        cache_key='key',
        request=request,
        settings=settings,
    )
    assert actions.expire_after == expected_expiration


@pytest.mark.parametrize(
    'headers, expected_expiration',
    [
        ({}, None),
        ({'Expires': HTTPDATE_STR}, None),  # Only valid for response headers
        ({'Cache-Control': 'max-age=60'}, 60),
        ({'Cache-Control': 'public, max-age=60'}, 60),
        ({'Cache-Control': 'max-age=0'}, DO_NOT_CACHE),
    ],
)
def test_init_from_headers(headers, expected_expiration):
    """Test with Cache-Control request headers"""
    settings = RequestSettings(cache_control=True)
    actions = CacheActions.from_request('key', MagicMock(headers=headers), settings)

    assert actions.cache_key == 'key'
    if expected_expiration == DO_NOT_CACHE:
        assert actions.skip_read is True
    else:
        assert actions.expire_after == expected_expiration
        assert actions.skip_read is False
        assert actions.skip_write is False


def test_init_from_headers__no_store():
    """Test with Cache-Control request headers"""
    settings = RequestSettings(cache_control=True)
    actions = CacheActions.from_request(
        'key', MagicMock(headers={'Cache-Control': 'no-store'}), settings
    )

    assert actions.skip_read is True
    assert actions.skip_write is True


@pytest.mark.parametrize(
    'url, request_expire_after, expected_expiration',
    [
        ('img.site_1.com', None, timedelta(hours=12)),
        ('img.site_1.com', 60, 60),
        ('http://img.site.com/base/', None, 1),
        ('https://img.site.com/base/img.jpg', None, 1),
        ('site_2.com/resource_1', None, timedelta(hours=20)),
        ('http://site_2.com/resource_1/index.html', None, timedelta(hours=20)),
        ('http://site_2.com/resource_2/', None, timedelta(days=7)),
        ('http://site_2.com/static/', None, -1),
        ('http://site_2.com/static/img.jpg', None, -1),
        ('site_2.com', None, 1),
        ('site_2.com', 60, 60),
        ('some_other_site.com', None, 1),
        ('some_other_site.com', 60, 60),
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
    request = MagicMock(url=url)
    if request_expire_after:
        request.headers = {'Cache-Control': f'max-age={request_expire_after}'}

    actions = CacheActions.from_request('key', request, RequestSettings.merge(settings))
    assert actions.expire_after == expected_expiration


@pytest.mark.parametrize(
    'headers, expire_after, expected_expiration, expected_skip_read',
    [
        ({'Cache-Control': 'max-age=60'}, 1, 60, False),
        ({}, 1, 1, False),
        ({}, 0, 0, True),
        ({'Cache-Control': 'max-age=60'}, 1, 60, False),
        ({'Cache-Control': 'max-age=0'}, 1, 0, True),
        ({'Cache-Control': 'no-store'}, 1, 1, True),
        ({'Cache-Control': 'no-cache'}, 1, 1, False),
    ],
)
def test_init_from_settings_and_headers(
    headers, expire_after, expected_expiration, expected_skip_read
):
    """Test behavior with both cache settings and request headers."""
    request = get_mock_response(headers=headers)
    settings = CacheSettings(expire_after=expire_after)
    actions = CacheActions.from_request('key', request, RequestSettings.merge(settings))

    assert actions.expire_after == expected_expiration
    assert actions.skip_read == expected_skip_read


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
def test_update_from_cached_response(response_headers, expected_validation_headers):
    """Conditional request headers should be added if the cached response is expired"""
    actions = CacheActions.from_request(
        'key',
        MagicMock(url='https://img.site.com/base/img.jpg', headers={}),
        RequestSettings(),
    )
    cached_response = CachedResponse(
        headers=response_headers, expires=datetime.now() - timedelta(1)
    )

    actions.update_from_cached_response(cached_response)
    assert actions._validation_headers == expected_validation_headers


@pytest.mark.parametrize(
    'request_headers, response_headers',
    [
        ({'Cache-Control': 'no-cache'}, {}),
        ({}, {'Cache-Control': 'no-cache'}),
        ({}, {'Cache-Control': 'max-age=0,must-revalidate'}),
    ],
)
def test_update_from_cached_response__revalidate_headers(request_headers, response_headers):
    """Conditional request headers should be added if requested by headers (even if the response
    is not expired)"""
    actions = CacheActions.from_request(
        'key',
        MagicMock(url='https://img.site.com/base/img.jpg', headers=request_headers),
        RequestSettings(),
    )
    cached_response = CachedResponse(headers={'ETag': ETAG, **response_headers}, expires=None)

    actions.update_from_cached_response(cached_response)
    assert actions._validation_headers == {'If-None-Match': ETAG}


def test_update_from_cached_response__ignored():
    """Conditional request headers should NOT be added if the cached response is not expired and
    revalidation is otherwise not requested"""
    actions = CacheActions.from_request(
        'key',
        MagicMock(url='https://img.site.com/base/img.jpg', headers={}),
        RequestSettings(),
    )
    cached_response = CachedResponse(
        headers={'ETag': ETAG, 'Last-Modified': LAST_MODIFIED}, expires=None
    )

    actions.update_from_cached_response(cached_response)
    assert actions._validation_headers == {}


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
    url = 'https://img.site.com/base/img.jpg'
    actions = CacheActions.from_request(
        'key', MagicMock(url=url), RequestSettings(cache_control=True)
    )
    actions.update_from_response(get_mock_response(headers=headers))

    assert actions.expire_after == expected_expiration
    assert actions.skip_write is (expected_expiration == DO_NOT_CACHE)


def test_update_from_response__no_store():
    url = 'https://img.site.com/base/img.jpg'
    actions = CacheActions.from_request(
        'key', MagicMock(url=url), RequestSettings(cache_control=True)
    )
    actions.update_from_response(get_mock_response(headers={'Cache-Control': 'no-store'}))
    assert actions.skip_write is True


def test_update_from_response__ignored():
    url = 'https://img.site.com/base/img.jpg'
    actions = CacheActions.from_request(
        'key', MagicMock(url=url), RequestSettings(cache_control=False)
    )
    actions.update_from_response(get_mock_response(headers={'Cache-Control': 'max-age=5'}))
    assert actions.expire_after is None


@pytest.mark.parametrize('validator_headers', [{'ETag': ETAG}, {'Last-Modified': LAST_MODIFIED}])
@pytest.mark.parametrize('cache_headers', [{'Cache-Control': 'max-age=0'}, {'Expires': '0'}])
@patch('requests_cache.expiration.datetime')
def test_update_from_response__revalidate(mock_datetime, cache_headers, validator_headers):
    """If expiration is 0 and there's a validator, the response should be cached, but with immediate
    expiration
    """
    url = 'https://img.site.com/base/img.jpg'
    actions = CacheActions.from_request(
        'key', MagicMock(url=url), RequestSettings(cache_control=True)
    )
    response = get_mock_response(headers={**cache_headers, **validator_headers})
    actions.update_from_response(response)

    assert actions.expires == mock_datetime.utcnow()
    assert actions.skip_write is False


@pytest.mark.parametrize('directive', IGNORED_DIRECTIVES)
def test_ignored_headers(directive):
    """Ensure that currently unimplemented Cache-Control headers do not affect behavior"""
    request = PreparedRequest()
    request.url = 'https://img.site.com/base/img.jpg'
    request.headers = {'Cache-Control': directive}
    settings = CacheSettings(expire_after=1, cache_control=True)
    actions = CacheActions.from_request('key', request, RequestSettings.merge(settings))

    assert actions.expire_after == 1
    assert actions.skip_read is False
    assert actions.skip_write is False
