"""BaseCache tests that use mocked responses only"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from requests_cache import CachedResponse
from requests_cache.backends import BaseCache, SQLiteDict
from tests.conftest import MOCKED_URL, MOCKED_URL_HTTPS, MOCKED_URL_JSON, MOCKED_URL_REDIRECT

YESTERDAY = datetime.utcnow() - timedelta(days=1)


class TimeBomb:
    """Class that will raise an error when unpickled"""

    def __init__(self):
        self.foo = 'bar'

    def __setstate__(self, value):
        raise ValueError('Invalid response!')


def test_urls__with_invalid_response(mock_session):
    responses = [mock_session.get(url) for url in [MOCKED_URL, MOCKED_URL_JSON, MOCKED_URL_HTTPS]]
    responses[2] = AttributeError
    with patch.object(SQLiteDict, '__getitem__', side_effect=responses):
        expected_urls = [MOCKED_URL, MOCKED_URL_JSON]
        assert set(mock_session.cache.urls) == set(expected_urls)

    # The invalid response should be skipped, but remain in the cache for now
    assert len(mock_session.cache.responses.keys()) == 3


def test_keys(mock_session):
    for url in [MOCKED_URL, MOCKED_URL_JSON, MOCKED_URL_REDIRECT]:
        mock_session.get(url)

    all_keys = set(mock_session.cache.responses.keys()) | set(mock_session.cache.redirects.keys())
    assert set(mock_session.cache.keys()) == all_keys


def test_update(mock_session):
    src_cache = BaseCache()
    for i in range(20):
        src_cache.responses[f'key_{i}'] = f'value_{i}'
        src_cache.redirects[f'key_{i}'] = f'value_{i}'

    mock_session.cache.update(src_cache)
    assert len(mock_session.cache.responses) == 20
    assert len(mock_session.cache.redirects) == 20


def test_values(mock_session):
    for url in [MOCKED_URL, MOCKED_URL_JSON, MOCKED_URL_HTTPS]:
        mock_session.get(url)

    responses = list(mock_session.cache.values())
    assert len(responses) == 3
    assert all([isinstance(response, CachedResponse) for response in responses])


@pytest.mark.parametrize('check_expiry, expected_count', [(True, 1), (False, 2)])
def test_values__with_invalid_responses(check_expiry, expected_count, mock_session):
    """values() should always exclude invalid responses, and optionally exclude expired responses"""
    responses = [mock_session.get(url) for url in [MOCKED_URL, MOCKED_URL_JSON, MOCKED_URL_HTTPS]]
    responses[1] = AttributeError
    responses[2] = CachedResponse(expires=YESTERDAY, url='test')

    with patch.object(SQLiteDict, '__getitem__', side_effect=responses):
        values = mock_session.cache.values(check_expiry=check_expiry)
        assert len(list(values)) == expected_count

    # The invalid response should be skipped, but remain in the cache for now
    assert len(mock_session.cache.responses.keys()) == 3


@pytest.mark.parametrize('check_expiry, expected_count', [(True, 2), (False, 3)])
def test_response_count(check_expiry, expected_count, mock_session):
    """response_count() should always exclude invalid responses, and optionally exclude expired
    and invalid responses"""
    mock_session.get(MOCKED_URL)
    mock_session.get(MOCKED_URL_JSON)

    mock_session.cache.responses['expired_response'] = CachedResponse(expires=YESTERDAY)
    mock_session.cache.responses['invalid_response'] = TimeBomb()
    assert mock_session.cache.response_count(check_expiry=check_expiry) == expected_count


def test_clear(mock_session):
    mock_session.get(MOCKED_URL)
    mock_session.get(MOCKED_URL_REDIRECT)
    mock_session.cache.clear()
    assert not mock_session.cache.has_url(MOCKED_URL)
    assert not mock_session.cache.has_url(MOCKED_URL_REDIRECT)


def test_has_url(mock_session):
    mock_session.get(MOCKED_URL)
    assert mock_session.cache.has_url(MOCKED_URL)
    assert not mock_session.cache.has_url(MOCKED_URL_REDIRECT)


def test_has_url__request_args(mock_session):
    mock_session.get(MOCKED_URL, params={'foo': 'bar'})
    assert mock_session.cache.has_url(MOCKED_URL, params={'foo': 'bar'})
    assert not mock_session.cache.has_url(MOCKED_URL)


def test_delete_url(mock_session):
    mock_session.get(MOCKED_URL)
    mock_session.cache.delete_url(MOCKED_URL)
    assert not mock_session.cache.has_url(MOCKED_URL)


def test_delete_url__request_args(mock_session):
    mock_session.get(MOCKED_URL, params={'foo': 'bar'})
    mock_session.cache.delete_url(MOCKED_URL, params={'foo': 'bar'})
    assert not mock_session.cache.has_url(MOCKED_URL, params={'foo': 'bar'})


def test_delete_url__nonexistent_response(mock_session):
    """Deleting a response that was either already deleted (or never added) should fail silently"""
    mock_session.cache.delete_url(MOCKED_URL)

    mock_session.get(MOCKED_URL)
    mock_session.cache.delete_url(MOCKED_URL)
    assert not mock_session.cache.has_url(MOCKED_URL)
    mock_session.cache.delete_url(MOCKED_URL)  # Should fail silently


def test_delete_url__redirect(mock_session):
    mock_session.get(MOCKED_URL_REDIRECT)
    assert mock_session.cache.has_url(MOCKED_URL_REDIRECT)

    mock_session.cache.delete_url(MOCKED_URL_REDIRECT)
    assert not mock_session.cache.has_url(MOCKED_URL_REDIRECT)


def test_delete_urls(mock_session):
    urls = [MOCKED_URL, MOCKED_URL_JSON, MOCKED_URL_REDIRECT]
    for url in urls:
        mock_session.get(url)

    mock_session.cache.delete_urls(urls)
    for url in urls:
        assert not mock_session.cache.has_url(MOCKED_URL_REDIRECT)


def test_save_response_manual(mock_session):
    response = mock_session.get(MOCKED_URL)
    mock_session.cache.clear()
    mock_session.cache.save_response(response)
