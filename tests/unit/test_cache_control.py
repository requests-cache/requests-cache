from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from requests import PreparedRequest

from requests_cache.cache_control import (
    DO_NOT_CACHE,
    CacheActions,
    get_expiration_datetime,
    get_url_expiration,
)
from requests_cache.models.response import CachedResponse
from tests.conftest import ETAG, HTTPDATE_DATETIME, HTTPDATE_STR, LAST_MODIFIED

IGNORED_DIRECTIVES = [
    'must-revalidate',
    'no-transform',
    'private',
    'proxy-revalidate',
    'public',
    's-maxage=<seconds>',
]


@pytest.mark.parametrize(
    'request_expire_after, url_expire_after, header_expire_after, expected_expiration',
    [
        (None, None, None, 1),
        (2, None, None, 2),
        (2, 3, None, 2),
        (None, 3, None, 3),
        (2, 3, 4, 4),
        (2, None, 4, 4),
        (None, 3, 4, 4),
        (None, None, 4, 4),
    ],
)
@patch('requests_cache.cache_control.get_url_expiration')
def test_init(
    get_url_expiration,
    request_expire_after,
    url_expire_after,
    header_expire_after,
    expected_expiration,
):
    """Test precedence with various combinations or per-request, per-session, per-URL, and
    Cache-Control expiration
    """
    request = PreparedRequest()
    request.url = 'https://img.site.com/base/img.jpg'
    request.headers = {'Cache-Control': f'max-age={header_expire_after}'} if header_expire_after else {}
    get_url_expiration.return_value = url_expire_after

    actions = CacheActions.from_request(
        cache_key='key',
        request=request,
        request_expire_after=request_expire_after,
        session_expire_after=1,
        cache_control=True,
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
        ({'Cache-Control': 'no-store'}, DO_NOT_CACHE),
    ],
)
def test_init_from_headers(headers, expected_expiration):
    """Test with Cache-Control request headers"""
    actions = CacheActions.from_request(
        cache_key='key', cache_control=True, request=MagicMock(headers=headers)
    )

    assert actions.cache_key == 'key'
    if expected_expiration == DO_NOT_CACHE:
        assert actions.skip_read is True
        assert actions.skip_write is True
    else:
        assert actions.expire_after == expected_expiration
        assert actions.skip_read is False
        assert actions.skip_write is False


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
    urls_expire_after = {
        '*.site_1.com': timedelta(hours=12),
        'site_2.com/resource_1': timedelta(hours=20),
        'site_2.com/resource_2': timedelta(days=7),
        'site_2.com/static': -1,
    }
    actions = CacheActions.from_request(
        cache_key='key',
        request=MagicMock(url=url),
        request_expire_after=request_expire_after,
        session_expire_after=1,
        urls_expire_after=urls_expire_after,
    )
    assert actions.expire_after == expected_expiration


@pytest.mark.parametrize(
    'response_headers, expected_request_headers',
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
def test_update_from_cached_response(response_headers, expected_request_headers):
    """Test with Cache-Control response headers"""
    actions = CacheActions.from_request(
        cache_key='key',
        request=MagicMock(url='https://img.site.com/base/img.jpg'),
        cache_control=True,
    )
    cached_response = CachedResponse(headers=response_headers, expires=datetime.now() - timedelta(1))
    actions.update_from_cached_response(cached_response)
    assert actions.add_request_headers == expected_request_headers


def test_update_from_cached_response__ignored():
    """Test with Cache-Control response headers"""
    # Do nothing if cache-control=Fase
    actions = CacheActions.from_request(
        cache_key='key',
        request=MagicMock(url='https://img.site.com/base/img.jpg'),
        cache_control=False,
    )
    cached_response = CachedResponse(
        headers={'ETag': ETAG, 'Last-Modified': LAST_MODIFIED},
        expires=datetime.now() - timedelta(1),
    )
    actions.update_from_cached_response(cached_response)
    assert actions.add_request_headers == {}

    # Do nothing if the response is not expired
    actions.cache_control = True
    cached_response.expires = None
    actions.update_from_cached_response(cached_response)
    assert actions.add_request_headers == {}


@pytest.mark.parametrize(
    'headers, expected_expiration',
    [
        ({}, None),
        ({'Cache-Control': 'no-cache'}, None),  # Only valid for request headers
        ({'Cache-Control': 'max-age=60'}, 60),
        ({'Cache-Control': 'public, max-age=60'}, 60),
        ({'Cache-Control': 'max-age=0'}, DO_NOT_CACHE),
        ({'Cache-Control': 'no-store'}, DO_NOT_CACHE),
        ({'Expires': HTTPDATE_STR}, HTTPDATE_STR),
        ({'Expires': HTTPDATE_STR, 'Cache-Control': 'max-age=60'}, 60),
    ],
)
def test_update_from_response(headers, expected_expiration):
    """Test with Cache-Control response headers"""
    url = 'https://img.site.com/base/img.jpg'
    actions = CacheActions.from_request(
        cache_key='key',
        request=MagicMock(url=url),
        cache_control=True,
    )
    actions.update_from_response(MagicMock(url=url, headers=headers))

    if expected_expiration == DO_NOT_CACHE:
        assert actions.skip_write is True
    else:
        assert actions.expire_after == expected_expiration
        assert actions.skip_write is False


def test_update_from_response__ignored():
    url = 'https://img.site.com/base/img.jpg'
    actions = CacheActions.from_request(
        cache_key='key',
        request=MagicMock(url=url),
        cache_control=False,
    )
    actions.update_from_response(MagicMock(url=url, headers={'Cache-Control': 'max-age=5'}))
    assert actions.expire_after is None


@pytest.mark.parametrize('directive', IGNORED_DIRECTIVES)
def test_ignored_headers(directive):
    """Ensure that currently unimplemented Cache-Control headers do not affect behavior"""
    request = PreparedRequest()
    request.url = 'https://img.site.com/base/img.jpg'
    request.headers = {'Cache-Control': directive}
    actions = CacheActions.from_request(
        cache_key='key',
        request=request,
        session_expire_after=1,
        cache_control=True,
    )
    assert actions.expire_after == 1


@patch('requests_cache.cache_control.datetime')
def test_get_expiration_datetime__no_expiration(mock_datetime):
    assert get_expiration_datetime(None) is None
    assert get_expiration_datetime(-1) is None
    assert get_expiration_datetime(DO_NOT_CACHE) == mock_datetime.utcnow()


@pytest.mark.parametrize(
    'expire_after, expected_expiration_delta',
    [
        (timedelta(seconds=60), timedelta(seconds=60)),
        (60, timedelta(seconds=60)),
        (33.3, timedelta(seconds=33.3)),
    ],
)
def test_get_expiration_datetime__relative(expire_after, expected_expiration_delta):
    expires = get_expiration_datetime(expire_after)
    expected_expiration = datetime.utcnow() + expected_expiration_delta
    # Instead of mocking datetime (which adds some complications), check for approximate value
    assert abs((expires - expected_expiration).total_seconds()) <= 1


def test_get_expiration_datetime__tzinfo():
    tz = timezone(-timedelta(hours=5))
    dt = datetime(2021, 2, 1, 7, 0, tzinfo=tz)
    assert get_expiration_datetime(dt) == datetime(2021, 2, 1, 12, 0)


def test_get_expiration_datetime__httpdate():
    assert get_expiration_datetime(HTTPDATE_STR) == HTTPDATE_DATETIME
    assert get_expiration_datetime('P12Y34M56DT78H90M12.345S') is None


@pytest.mark.parametrize(
    'url, expected_expire_after',
    [
        ('img.site_1.com', 60 * 60),
        ('http://img.site_1.com/base/img.jpg', 60 * 60),
        ('https://img.site_2.com/base/img.jpg', None),
        ('site_2.com/resource_1', 60 * 60 * 2),
        ('http://site_2.com/resource_1/index.html', 60 * 60 * 2),
        ('http://site_2.com/resource_2/', 60 * 60 * 24),
        ('http://site_2.com/static/', -1),
        ('http://site_2.com/static/img.jpg', -1),
        ('site_2.com', None),
        ('some_other_site.com', None),
        (None, None),
    ],
)
def test_get_url_expiration(url, expected_expire_after, mock_session):
    urls_expire_after = {
        '*.site_1.com': 60 * 60,
        'site_2.com/resource_1': 60 * 60 * 2,
        'site_2.com/resource_2': 60 * 60 * 24,
        'site_2.com/static': -1,
    }
    assert get_url_expiration(url, urls_expire_after) == expected_expire_after


@pytest.mark.parametrize(
    'url, expected_expire_after',
    [
        ('https://img.site_1.com/image.jpeg', 60 * 60),
        ('https://img.site_1.com/resource/1', 60 * 60 * 2),
        ('https://site_2.com', 1),
        ('https://any_other_site.com', 1),
    ],
)
def test_get_url_expiration__evaluation_order(url, expected_expire_after):
    """If there are multiple matches, the first match should be used in the order defined"""
    urls_expire_after = {
        '*.site_1.com/resource': 60 * 60 * 2,
        '*.site_1.com': 60 * 60,
        '*': 1,
    }
    assert get_url_expiration(url, urls_expire_after) == expected_expire_after
