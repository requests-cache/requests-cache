"""BaseCache tests that use mocked responses only"""
import pickle
from datetime import datetime, timedelta
from logging import getLogger
from pickle import PickleError
from time import sleep
from unittest.mock import patch

import pytest
from requests import Request

from requests_cache.backends import BaseCache, SQLiteCache, SQLiteDict
from requests_cache.cache_keys import create_key
from requests_cache.models import CachedRequest, CachedResponse
from requests_cache.session import CachedSession
from tests.conftest import (
    MOCKED_URL,
    MOCKED_URL_ETAG,
    MOCKED_URL_HTTPS,
    MOCKED_URL_JSON,
    MOCKED_URL_REDIRECT,
    ignore_deprecation,
    mount_mock_adapter,
    patch_normalize_url,
)

YESTERDAY = datetime.utcnow() - timedelta(days=1)
logger = getLogger(__name__)


class InvalidResponse:
    """Class that will raise an error when unpickled"""

    def __init__(self):
        self.foo = 'bar'

    def __setstate__(self, value):
        raise ValueError('Invalid response!')


def test_contains__key(mock_session):
    mock_session.get(MOCKED_URL, params={'foo': 'bar'})
    key = list(mock_session.cache.responses.keys())[0]
    assert mock_session.cache.contains(key)
    assert not mock_session.cache.contains(f'{key}_b')


def test_contains__request(mock_session):
    mock_session.get(MOCKED_URL, params={'foo': 'bar'})
    request = Request('GET', MOCKED_URL, params={'foo': 'bar'})
    assert mock_session.cache.contains(request=request)
    request.params = None
    assert not mock_session.cache.contains(request=request)


def test_contains__url(mock_session):
    mock_session.get(MOCKED_URL)
    assert mock_session.cache.contains(url=MOCKED_URL)
    assert not mock_session.cache.contains(url=f'{MOCKED_URL}?foo=bar')


@patch_normalize_url
def test_delete__expired(mock_normalize_url, mock_session):
    unexpired_url = f'{MOCKED_URL}?x=1'
    mock_session.mock_adapter.register_uri(
        'GET', unexpired_url, status_code=200, text='mock response'
    )
    mock_session.settings.expire_after = 1
    mock_session.get(MOCKED_URL)
    mock_session.get(MOCKED_URL_JSON)
    sleep(1.1)
    mock_session.settings.expire_after = 2
    mock_session.get(unexpired_url)

    # At this point we should have 1 unexpired response and 2 expired responses
    assert len(mock_session.cache.responses) == 3

    # Use the generic BaseCache implementation, not the SQLite-specific one
    BaseCache.delete(mock_session.cache, expired=True)
    assert len(mock_session.cache.responses) == 1
    cached_response = list(mock_session.cache.responses.values())[0]
    assert cached_response.url == unexpired_url

    # Now the last response should be expired as well
    sleep(2)
    BaseCache.delete(mock_session.cache, expired=True)
    assert len(mock_session.cache.responses) == 0


def test_delete__expired__per_request(mock_session):
    # Cache 3 responses with different expiration times
    second_url = f'{MOCKED_URL}/endpoint_2'
    third_url = f'{MOCKED_URL}/endpoint_3'
    mock_session.mock_adapter.register_uri('GET', second_url, status_code=200)
    mock_session.mock_adapter.register_uri('GET', third_url, status_code=200)
    mock_session.get(MOCKED_URL)
    mock_session.get(second_url, expire_after=2)
    mock_session.get(third_url, expire_after=4)

    # All 3 responses should still be cached
    mock_session.cache.delete(expired=True)
    for response in mock_session.cache.responses.values():
        logger.info(f'Expires in {response.expires_delta} seconds')
    assert len(mock_session.cache.responses) == 3

    # One should be expired after 2s, and another should be expired after 4s
    sleep(2)
    mock_session.cache.delete(expired=True)
    assert len(mock_session.cache.responses) == 2
    sleep(2)
    mock_session.cache.delete(expired=True)
    assert len(mock_session.cache.responses) == 1


def test_delete__invalid(tempfile_path):
    class BadSerialzier:
        def dumps(self, value):
            return pickle.dumps(value)

        def loads(self, value):
            response = pickle.loads(value)
            if response.url.endswith('/json'):
                raise PickleError
            return response

    mock_session = CachedSession(
        cache_name=tempfile_path, backend='sqlite', serializer=BadSerialzier()
    )
    mock_session = mount_mock_adapter(mock_session)

    # Start with two cached responses, one of which will raise an error
    response_1 = mock_session.get(MOCKED_URL)
    response_2 = mock_session.get(MOCKED_URL_JSON)

    # Use the generic BaseCache implementation, not the SQLite-specific one
    BaseCache.delete(mock_session.cache, expired=True, invalid=True)

    assert len(mock_session.cache.responses) == 1
    assert mock_session.get(MOCKED_URL).from_cache is True
    assert mock_session.get(MOCKED_URL_JSON).from_cache is False


def test_delete__older_than(mock_session):
    # Cache 4 responses with different creation times
    response_0 = CachedResponse(request=CachedRequest(method='GET', url='https://test.com/test_0'))
    mock_session.cache.save_response(response_0)
    response_1 = CachedResponse(request=CachedRequest(method='GET', url='https://test.com/test_1'))
    response_1.created_at -= timedelta(seconds=1)
    mock_session.cache.save_response(response_1)
    response_2 = CachedResponse(request=CachedRequest(method='GET', url='https://test.com/test_2'))
    response_2.created_at -= timedelta(seconds=2)
    mock_session.cache.save_response(response_2)
    response_3 = CachedResponse(request=CachedRequest(method='GET', url='https://test.com/test_3'))
    response_3.created_at -= timedelta(seconds=3)
    mock_session.cache.save_response(response_3)

    # Incrementally remove responses older than 3, 2, and 1 seconds
    assert len(mock_session.cache.responses) == 4
    mock_session.cache.delete(older_than=timedelta(seconds=3))
    assert len(mock_session.cache.responses) == 3
    mock_session.cache.delete(older_than=timedelta(seconds=2))
    assert len(mock_session.cache.responses) == 2
    mock_session.cache.delete(older_than=timedelta(seconds=1))
    assert len(mock_session.cache.responses) == 1

    # Remove the last response after it's 1 second old
    sleep(1)
    mock_session.cache.delete(older_than=timedelta(seconds=1))
    assert len(mock_session.cache.responses) == 0


def test_delete__urls(mock_session):
    urls = [MOCKED_URL, MOCKED_URL_JSON, MOCKED_URL_REDIRECT]
    for url in urls:
        mock_session.get(url)

    mock_session.cache.delete(urls=urls)

    for url in urls:
        assert not mock_session.cache.contains(url=url)


def test_delete__requests(mock_session):
    urls = [MOCKED_URL, MOCKED_URL_JSON, MOCKED_URL_REDIRECT]
    for url in urls:
        mock_session.get(url)

    requests = [Request('GET', url).prepare() for url in urls]
    mock_session.cache.delete(requests=requests)

    for request in requests:
        assert not mock_session.cache.contains(request=request)


def test_recreate_keys(mock_session):
    # Cache some initial responses with default key function
    urls = [MOCKED_URL, MOCKED_URL_JSON, MOCKED_URL_ETAG]
    for url in urls:
        mock_session.get(url)
    old_cache_keys = set(mock_session.cache.responses.keys())

    # Switch to a new key function and recreate keys
    def new_key_fn(*args, **kwargs):
        return create_key(*args, **kwargs) + '_suffix'

    # Check that responses are saved with new keys
    mock_session.settings.key_fn = new_key_fn
    mock_session.cache.recreate_keys()
    new_cache_keys = set(mock_session.cache.responses.keys())
    assert len(old_cache_keys) == len(new_cache_keys) == len(urls)
    assert old_cache_keys != new_cache_keys

    # Check that responses are returned from the cache correctly using the new key function
    for url in urls:
        assert mock_session.get(url).from_cache is True


def test_recreate_keys__same_key_fn(mock_session):
    urls = [MOCKED_URL, MOCKED_URL_JSON, MOCKED_URL_ETAG]
    for url in urls:
        mock_session.get(url)
    old_cache_keys = set(mock_session.cache.responses.keys())

    mock_session.cache.recreate_keys()
    new_cache_keys = set(mock_session.cache.responses.keys())
    assert old_cache_keys == new_cache_keys

    # Check that responses are returned from the cache correctly using the new key function
    for url in urls:
        assert mock_session.get(url).from_cache is True


def test_reset_expiration__extend_expiration(mock_session):
    # Start with an expired response
    mock_session.settings.expire_after = datetime.utcnow() - timedelta(seconds=1)
    mock_session.get(MOCKED_URL)

    # Set expiration in the future
    mock_session.cache.reset_expiration(datetime.utcnow() + timedelta(seconds=1))
    assert len(mock_session.cache.responses) == 1
    response = mock_session.get(MOCKED_URL)
    assert response.is_expired is False and response.from_cache is True


def test_reset_expiration__shorten_expiration(mock_session):
    # Start with a non-expired response
    mock_session.settings.expire_after = datetime.utcnow() + timedelta(seconds=1)
    mock_session.get(MOCKED_URL)

    # Set expiration in the past
    mock_session.cache.reset_expiration(datetime.utcnow() - timedelta(seconds=1))
    response = mock_session.get(MOCKED_URL)
    assert response.is_expired is False and response.from_cache is False


def test_clear(mock_session):
    mock_session.get(MOCKED_URL)
    mock_session.get(MOCKED_URL_REDIRECT)
    mock_session.cache.clear()
    assert not mock_session.cache.contains(url=MOCKED_URL)
    assert not mock_session.cache.contains(url=MOCKED_URL_REDIRECT)


def test_save_response__manual(mock_session):
    response = mock_session.get(MOCKED_URL)
    mock_session.cache.clear()
    mock_session.cache.save_response(response)


def test_update(mock_session):
    src_cache = BaseCache()
    for i in range(20):
        src_cache.responses[f'key_{i}'] = f'value_{i}'
        src_cache.redirects[f'key_{i}'] = f'value_{i}'

    mock_session.cache.update(src_cache)
    assert len(mock_session.cache.responses) == 20
    assert len(mock_session.cache.redirects) == 20


@patch_normalize_url
def test_urls(mock_normalize_url, mock_session):
    for url in [MOCKED_URL, MOCKED_URL, MOCKED_URL_JSON, MOCKED_URL_HTTPS]:
        mock_session.get(url)

    expected_urls = [MOCKED_URL_JSON, MOCKED_URL, MOCKED_URL_HTTPS]
    assert mock_session.cache.urls() == expected_urls


def test_urls__error(mock_session):
    responses = [mock_session.get(url) for url in [MOCKED_URL, MOCKED_URL_JSON, MOCKED_URL_HTTPS]]
    responses[2] = None
    with patch.object(SQLiteDict, 'deserialize', side_effect=responses):
        expected_urls = [MOCKED_URL_JSON, MOCKED_URL]
        assert mock_session.cache.urls() == expected_urls

    # The invalid response should be skipped, but remain in the cache
    assert len(mock_session.cache.responses.keys()) == 3


# Deprecated methods
# --------------------


def test_has_key(mock_session):
    response = CachedResponse()
    mock_session.cache.responses['12345'] = response
    # flake8: noqa: W601
    assert mock_session.cache.has_key('12345')
    assert not mock_session.cache.has_key('1234')


def test_has_url(mock_session):
    mock_session.get(MOCKED_URL, params={'foo': 'bar'})
    with ignore_deprecation():
        assert mock_session.cache.has_url(MOCKED_URL, params={'foo': 'bar'})
        assert not mock_session.cache.has_url(MOCKED_URL)


def test_delete_url(mock_session):
    mock_session.get(MOCKED_URL)
    with ignore_deprecation():
        mock_session.cache.delete_url(MOCKED_URL)
        assert not mock_session.cache.has_url(MOCKED_URL)


def test_delete_url__request_args(mock_session):
    mock_session.get(MOCKED_URL, params={'foo': 'bar'})
    with ignore_deprecation():
        mock_session.cache.delete_url(MOCKED_URL, params={'foo': 'bar'})
        assert not mock_session.cache.has_url(MOCKED_URL, params={'foo': 'bar'})


def test_delete_url__nonexistent_response(mock_session):
    """Deleting a response that was either already deleted (or never added) should fail silently"""
    with ignore_deprecation():
        mock_session.cache.delete_url(MOCKED_URL)

        mock_session.get(MOCKED_URL)
        mock_session.cache.delete_url(MOCKED_URL)

        assert not mock_session.cache.has_url(MOCKED_URL)
        mock_session.cache.delete_url(MOCKED_URL)  # Should fail silently


def test_delete_urls(mock_session):
    mock_session.get(MOCKED_URL)
    with ignore_deprecation():
        mock_session.cache.delete_urls([MOCKED_URL])
        assert not mock_session.cache.has_url(MOCKED_URL)


def test_keys(mock_session):
    for url in [MOCKED_URL, MOCKED_URL_JSON, MOCKED_URL_REDIRECT]:
        mock_session.get(url)

    with ignore_deprecation():
        response_keys = set(mock_session.cache.responses.keys())
        redirect_keys = set(mock_session.cache.redirects.keys())
        assert set(mock_session.cache.keys()) == response_keys | redirect_keys
        assert len(list(mock_session.cache.keys(check_expiry=True))) == 5


def test_remove_expired_responses(mock_session):
    """Test for backwards-compatibility"""
    with ignore_deprecation(), patch.object(
        mock_session.cache, 'delete'
    ) as mock_delete, patch.object(mock_session.cache, 'reset_expiration') as mock_reset:
        mock_session.cache.remove_expired_responses(expire_after=1)
        mock_delete.assert_called_once_with(expired=True, invalid=True)
        mock_reset.assert_called_once_with(1)

        mock_session.cache.remove_expired_responses()
        assert mock_delete.call_count == 2 and mock_reset.call_count == 1


@pytest.mark.parametrize('check_expiry, expected_count', [(True, 2), (False, 3)])
def test_response_count(check_expiry, expected_count, mock_session):
    """response_count() should always exclude invalid responses, and optionally exclude expired
    responses"""
    mock_session.get(MOCKED_URL)
    mock_session.get(MOCKED_URL_JSON)

    mock_session.cache.responses['expired_response'] = CachedResponse(expires=YESTERDAY)
    mock_session.cache.responses['invalid_response'] = InvalidResponse()
    with ignore_deprecation():
        response_count = mock_session.cache.response_count(check_expiry=check_expiry)
    assert response_count == expected_count


def test_values(mock_session):
    for url in [MOCKED_URL, MOCKED_URL_JSON, MOCKED_URL_HTTPS]:
        mock_session.get(url)

    with ignore_deprecation():
        responses = list(mock_session.cache.values())
    assert len(responses) == 3
    assert all([isinstance(response, CachedResponse) for response in responses])


def test_values__with_invalid_responses(mock_session):
    responses = [mock_session.get(url) for url in [MOCKED_URL, MOCKED_URL_JSON, MOCKED_URL_HTTPS]]
    responses[1] = None
    responses[2] = CachedResponse(expires=YESTERDAY, url='test')

    with ignore_deprecation(), patch.object(SQLiteCache, 'filter', side_effect=responses):
        values = mock_session.cache.values(check_expiry=True)
        assert len(list(values)) == 1

    # The invalid response should be skipped, but remain in the cache for now
    assert len(mock_session.cache.responses.keys()) == 3
