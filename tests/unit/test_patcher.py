from unittest.mock import patch

import requests
from requests.sessions import Session as OriginalSession

import requests_cache
from requests_cache import CachedSession
from requests_cache.backends import BaseCache, DbCache
from tests.conftest import CACHE_NAME


def test_install_uninstall():
    for _ in range(2):
        requests_cache.install_cache(name=CACHE_NAME, use_temp=True)
        assert isinstance(requests.Session(), CachedSession)
        assert isinstance(requests.sessions.Session(), CachedSession)
        requests_cache.uninstall_cache()
        assert not isinstance(requests.Session(), CachedSession)
        assert not isinstance(requests.sessions.Session(), CachedSession)


def test_session_is_a_class_with_original_attributes(installed_session):
    assert isinstance(requests.Session, type)
    for attribute in dir(OriginalSession):
        assert hasattr(requests.Session, attribute)
    assert isinstance(requests.Session(), CachedSession)


def test_inheritance_after_monkey_patch(installed_session):
    class FooSession(requests.Session):
        __attrs__ = requests.Session.__attrs__ + ["new_one"]

        def __init__(self, param):
            self.param = param
            super(FooSession, self).__init__()

    s = FooSession(1)
    assert isinstance(s, CachedSession)
    assert s.param == 1
    assert "new_one" in s.__attrs__


@patch.object(DbCache, 'clear')
def test_clear(mock_clear, installed_session):
    requests_cache.clear()
    mock_clear.assert_called()


@patch.object(DbCache, 'clear')
def test_clear__not_installed(mock_clear):
    """If clear is called without a cache installed, it should just fail silently"""
    requests_cache.clear()
    mock_clear.assert_not_called()


@patch.object(OriginalSession, 'request')
@patch.object(CachedSession, 'request')
def test_disabled(cached_request, original_request, installed_session):
    with requests_cache.disabled():
        for i in range(3):
            requests.get('some_url')
    assert cached_request.call_count == 0
    assert original_request.call_count == 3


@patch.object(OriginalSession, 'request')
@patch.object(CachedSession, 'request')
def test_enabled(cached_request, original_request, tempfile_path):
    with requests_cache.enabled(tempfile_path):
        for i in range(3):
            requests.get('some_url')
    assert cached_request.call_count == 3
    assert original_request.call_count == 0


@patch.object(BaseCache, 'remove_expired_responses')
def test_remove_expired_responses(remove_expired_responses, tempfile_path):
    requests_cache.install_cache(tempfile_path, expire_after=360)
    requests_cache.remove_expired_responses()
    assert remove_expired_responses.called is True
    requests_cache.uninstall_cache()


@patch.object(BaseCache, 'remove_expired_responses')
def test_remove_expired_responses__cache_not_installed(remove_expired_responses):
    requests_cache.remove_expired_responses()
    assert remove_expired_responses.called is False


@patch.object(BaseCache, 'remove_expired_responses')
def test_remove_expired_responses__no_expiration(remove_expired_responses, installed_session):
    requests_cache.remove_expired_responses()
    assert remove_expired_responses.called is True
