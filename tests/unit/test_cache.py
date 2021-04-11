"""CachedSession + BaseCache tests that use mocked responses only"""
# TODO: This could be split up into some smaller test modules
import json
import pickle
import pytest
import time
from collections import UserDict, defaultdict
from datetime import datetime, timedelta
from pickle import PickleError
from unittest.mock import patch
from uuid import uuid4

import requests
from itsdangerous.exc import BadSignature
from itsdangerous.serializer import Serializer
from requests.structures import CaseInsensitiveDict

from requests_cache import ALL_METHODS, CachedSession
from requests_cache.backends import BACKEND_CLASSES, BaseCache, get_placeholder_backend
from requests_cache.backends.sqlite import DbDict, DbPickleDict
from tests.conftest import (
    MOCKED_URL,
    MOCKED_URL_HTTPS,
    MOCKED_URL_JSON,
    MOCKED_URL_REDIRECT,
    MOCKED_URL_REDIRECT_TARGET,
)


def test_init_unregistered_backend():
    with pytest.raises(ValueError):
        CachedSession(backend='nonexistent')


@patch.dict(BACKEND_CLASSES, {'mongo': get_placeholder_backend()})
def test_init_missing_backend_dependency():
    """Test that the correct error is thrown when a user does not have a dependency installed"""
    with pytest.raises(ImportError):
        CachedSession(backend='mongo')


class MyCache(BaseCache):
    pass


def test_init_backend_instance():
    backend = MyCache()
    session = CachedSession(backend=backend)
    assert session.cache is backend


def test_init_backend_class():
    session = CachedSession(backend=MyCache)
    assert isinstance(session.cache, MyCache)


def test_import_compat():
    """Just make sure that we can still import from requests_cache.core"""
    with pytest.deprecated_call():
        from requests_cache.core import CachedSession, install_cache  # noqa: F401


def test_method_compat(mock_session):
    with pytest.deprecated_call():
        mock_session.cache.remove_old_entries()


@pytest.mark.parametrize('method', ALL_METHODS)
@pytest.mark.parametrize('field', ['params', 'data', 'json'])
def test_all_methods(field, method, mock_session):
    """Test all relevant combinations of methods and data fields. Requests with different request
    params, data, or json should be cached under different keys.
    """
    for params in [{'param_1': 1}, {'param_1': 2}, {'param_2': 2}]:
        assert mock_session.request(method, MOCKED_URL, **{field: params}).from_cache is False
        assert mock_session.request(method, MOCKED_URL, **{field: params}).from_cache is True


@pytest.mark.parametrize('method', ALL_METHODS)
@pytest.mark.parametrize('field', ['params', 'data', 'json'])
def test_all_methods__ignore_parameters(field, method, mock_session):
    """Test all relevant combinations of methods and data fields. Requests with different request
    params, data, or json should not be cached under different keys based on an ignored param.
    """
    mock_session.cache._ignored_parameters = ['ignored']
    params_1 = {'ignored': 1, 'not ignored': 1}
    params_2 = {'ignored': 2, 'not ignored': 1}
    params_3 = {'ignored': 2, 'not ignored': 2}

    assert mock_session.request(method, MOCKED_URL, **{field: params_1}).from_cache is False
    assert mock_session.request(method, MOCKED_URL, **{field: params_1}).from_cache is True
    assert mock_session.request(method, MOCKED_URL, **{field: params_2}).from_cache is True
    mock_session.request(method, MOCKED_URL, params={'a': 'b'})
    assert mock_session.request(method, MOCKED_URL, **{field: params_3}).from_cache is False


def test_https(mock_session):
    assert mock_session.get(MOCKED_URL_HTTPS, verify=True).from_cache is False
    assert mock_session.get(MOCKED_URL_HTTPS, verify=True).from_cache is True


def test_json(mock_session):
    assert mock_session.get(MOCKED_URL_JSON).from_cache is False
    response = mock_session.get(MOCKED_URL_JSON)
    assert response.from_cache is True
    assert response.json()['message'] == 'mock json response'


def test_verify(mock_session):
    mock_session.get(MOCKED_URL)
    assert mock_session.get(MOCKED_URL).from_cache is True
    assert mock_session.get(MOCKED_URL, verify=False).from_cache is False
    assert mock_session.get(MOCKED_URL, verify='/path/to/cert').from_cache is False


def test_response_history(mock_session):
    mock_session.get(MOCKED_URL_REDIRECT)
    r = mock_session.get(MOCKED_URL_REDIRECT_TARGET)

    assert r.from_cache is True
    assert len(mock_session.cache.redirects) == 1


def test_repr():
    """Test session and cache string representations"""
    cache_name = 'requests_cache_test'
    session = CachedSession(cache_name=cache_name, backend='memory', expire_after=10)
    session.cache.responses['key'] = 'value'
    session.cache.redirects['key'] = 'value'
    session.cache.redirects['key_2'] = 'value'

    assert cache_name in repr(session) and '10' in repr(session)
    assert 'redirects: 2' in str(session.cache) and 'responses: 1' in str(session.cache)


def test_cached_urls(mock_session):
    for url in [MOCKED_URL, MOCKED_URL_JSON, MOCKED_URL_HTTPS]:
        mock_session.get(url)

    expected_urls = [MOCKED_URL, MOCKED_URL_JSON, MOCKED_URL_HTTPS]
    assert set(mock_session.cache.urls) == set(expected_urls)


def test_invalid_urls(mock_session):
    responses = [mock_session.get(url) for url in [MOCKED_URL, MOCKED_URL_JSON, MOCKED_URL_HTTPS]]
    responses[2] = AttributeError
    with patch.object(DbPickleDict, '__getitem__', side_effect=responses):
        expected_urls = [MOCKED_URL, MOCKED_URL_JSON]
        assert set(mock_session.cache.urls) == set(expected_urls)


def test_filter_fn(mock_session):
    mock_session.filter_fn = lambda r: r.url != MOCKED_URL_JSON
    mock_session.get(MOCKED_URL)
    mock_session.get(MOCKED_URL_JSON)

    assert mock_session.cache.has_url(MOCKED_URL)
    assert not mock_session.cache.has_url(MOCKED_URL_JSON)


def test_filter_fn__retroactive(mock_session):
    """filter_fn should also apply to previously cached responses"""
    mock_session.get(MOCKED_URL_JSON)
    mock_session.filter_fn = lambda r: r.url != MOCKED_URL_JSON
    mock_session.get(MOCKED_URL_JSON)

    assert not mock_session.cache.has_url(MOCKED_URL_JSON)


def test_hooks(mock_session):
    state = defaultdict(int)
    mock_session.get(MOCKED_URL)

    for hook in ('response',):

        def hook_func(r, *args, **kwargs):
            state[hook] += 1
            assert r.from_cache is True
            return r

        for i in range(5):
            mock_session.get(MOCKED_URL, hooks={hook: hook_func})
        assert state[hook] == 5


@pytest.mark.parametrize('method', ['POST', 'PUT'])
def test_raw_data(method, mock_session):
    """POST and PUT requests with different data (raw) should be cached under different keys"""
    assert mock_session.request(method, MOCKED_URL, data='raw data').from_cache is False
    assert mock_session.request(method, MOCKED_URL, data='raw data').from_cache is True
    assert mock_session.request(method, MOCKED_URL, data='new raw data').from_cache is False


@pytest.mark.parametrize('mapping_class', [dict, UserDict, CaseInsensitiveDict])
@pytest.mark.parametrize('field', ['params', 'data', 'json'])
def test_normalize_params(field, mapping_class, mock_session):
    """Test normalization with different combinations of data fields and dict-like classes"""
    params = {"a": "a", "b": ["1", "2", "3"], "c": "4"}
    reversed_params = mapping_class(sorted(params.items(), reverse=True))

    assert mock_session.get(MOCKED_URL, **{field: params}).from_cache is False
    assert mock_session.get(MOCKED_URL, **{field: params}).from_cache is True
    assert mock_session.post(MOCKED_URL, **{field: params}).from_cache is False
    assert mock_session.post(MOCKED_URL, **{field: params}).from_cache is True
    assert mock_session.post(MOCKED_URL, **{field: reversed_params}).from_cache is True
    assert mock_session.post(MOCKED_URL, **{field: {"a": "b"}}).from_cache is False


@pytest.mark.parametrize('field', ['data', 'json'])
def test_normalize_serialized_body(field, mock_session):
    """Test normalization for serialized request body content"""
    params = {"a": "a", "b": ["1", "2", "3"], "c": "4"}
    reversed_params = dict(sorted(params.items(), reverse=True))

    assert mock_session.post(MOCKED_URL, **{field: json.dumps(params)}).from_cache is False
    assert mock_session.post(MOCKED_URL, **{field: json.dumps(params)}).from_cache is True
    assert mock_session.post(MOCKED_URL, **{field: json.dumps(reversed_params)}).from_cache is True


def test_normalize_non_json_body(mock_session):
    """For serialized request body content that isn't in JSON format, no normalization is expected"""
    assert mock_session.post(MOCKED_URL, data=b'key_1=value_1,key_2=value_2').from_cache is False
    assert mock_session.post(MOCKED_URL, data=b'key_1=value_1,key_2=value_2').from_cache is True
    assert mock_session.post(MOCKED_URL, data=b'key_2=value_2,key_1=value_1').from_cache is False


def test_normalize_url(mock_session):
    """Test URL variations that should all result in the same key"""
    urls = [
        'https://site.com?param_1=value_1&param_2=value_2',
        'https://site.com?param_2=value_2&param_1=value_1',
        'https://site.com:443?param_1=value_1&param_2=value_2',
        'HTTPS://site.com?param_1=value_1&param_2=value_2',
    ]

    def get_request(url):
        return mock_session.prepare_request(requests.Request('GET', url))

    keys = [mock_session.cache.create_key(get_request(url)) for url in urls]
    assert len(set(keys)) == 1


def test_clear(mock_session):
    mock_session.get(MOCKED_URL)
    mock_session.get(MOCKED_URL_REDIRECT)
    mock_session.cache.clear()
    assert not mock_session.cache.has_url(MOCKED_URL)
    assert not mock_session.cache.has_url(MOCKED_URL_REDIRECT)


def test_delete_response(mock_session):
    mock_session.get(MOCKED_URL)
    mock_session.cache.delete_url(MOCKED_URL)
    assert not mock_session.cache.has_url(MOCKED_URL)


def test_delete_nonexistent_response(mock_session):
    """Deleting a response that was either already deleted (or never added) should fail silently"""
    mock_session.cache.delete_url(MOCKED_URL)

    mock_session.get(MOCKED_URL)
    mock_session.cache.delete_url(MOCKED_URL)
    assert not mock_session.cache.has_url(MOCKED_URL)
    mock_session.cache.delete_url(MOCKED_URL)  # Should fail silently


def test_delete_redirect(mock_session):
    mock_session.get(MOCKED_URL_REDIRECT)
    assert mock_session.cache.has_url(MOCKED_URL_REDIRECT)

    mock_session.cache.delete_url(MOCKED_URL_REDIRECT)
    assert not mock_session.cache.has_url(MOCKED_URL_REDIRECT)


def test_response_defaults(mock_session):
    """Both cached and new responses should always have the following attributes"""
    mock_session.expire_after = datetime.utcnow() + timedelta(days=1)
    response_1 = mock_session.get(MOCKED_URL)
    response_2 = mock_session.get(MOCKED_URL)
    response_3 = mock_session.get(MOCKED_URL)

    assert response_1.created_at is None
    assert response_1.expires is None
    assert response_1.from_cache is False
    assert response_1.is_expired is False

    assert isinstance(response_2.created_at, datetime)
    assert isinstance(response_2.expires, datetime)
    assert response_2.created_at == response_3.created_at
    assert response_2.expires == response_3.expires
    assert response_2.from_cache is response_3.from_cache is True
    assert response_2.is_expired is response_3.is_expired is False


def test_include_get_headers(mock_session):
    """With include_get_headers, requests with different headers should have different cache keys"""
    mock_session.cache._include_get_headers = True
    headers_list = [{'Accept': 'text/json'}, {'Accept': 'text/xml'}, {'Accept': 'custom'}, None]
    for headers in headers_list:
        assert mock_session.get(MOCKED_URL, headers=headers).from_cache is False
        assert mock_session.get(MOCKED_URL, headers=headers).from_cache is True


def test_include_get_headers_normalize(mock_session):
    """With include_get_headers, the same headers (in any order) should have the same cache key"""
    mock_session.cache._include_get_headers = True
    headers = {'Accept': 'text/json', 'Custom': 'abc'}
    reversed_headers = {'Custom': 'abc', 'Accept': 'text/json'}
    assert mock_session.get(MOCKED_URL, headers=headers).from_cache is False
    assert mock_session.get(MOCKED_URL, headers=reversed_headers).from_cache is True


@pytest.mark.parametrize(
    'exception_cls',
    [AttributeError, KeyError, TypeError, ValueError, pickle.PickleError],
)
def test_cache_error(exception_cls, mock_session):
    """If there is an error while fetching a cached response, a new one should be fetched"""
    mock_session.get(MOCKED_URL)
    with patch.object(DbDict, '__getitem__', side_effect=exception_cls):
        assert mock_session.get(MOCKED_URL).from_cache is False


def test_expired_request_error(mock_session):
    """Without old_data_on_error (default), if there is an error while re-fetching an expired
    response, the request should be re-raised and the expired item deleted"""
    mock_session.old_data_on_error = False
    mock_session.expire_after = 0.01
    mock_session.get(MOCKED_URL)
    time.sleep(0.01)

    with patch.object(mock_session.cache, 'save_response', side_effect=ValueError):
        with pytest.raises(ValueError):
            mock_session.get(MOCKED_URL)
    assert len(mock_session.cache.responses) == 0


def test_old_data_on_error(mock_session):
    """With old_data_on_error, expect to get old cache data if there is an error during a request"""
    mock_session.old_data_on_error = True
    mock_session.expire_after = 0.2

    assert mock_session.get(MOCKED_URL).from_cache is False
    assert mock_session.get(MOCKED_URL).from_cache is True
    time.sleep(0.2)
    with patch.object(mock_session.cache, 'save_response', side_effect=ValueError):
        response = mock_session.get(MOCKED_URL)
        assert response.from_cache is True and response.is_expired is True


def test_cache_disabled(mock_session):
    mock_session.get(MOCKED_URL)
    with mock_session.cache_disabled():
        for i in range(2):
            assert mock_session.get(MOCKED_URL).from_cache is False
    assert mock_session.get(MOCKED_URL).from_cache is True


def test_cache_disabled__nested(mock_session):
    mock_session.get(MOCKED_URL)
    with mock_session.cache_disabled():
        mock_session.get(MOCKED_URL)
        with mock_session.cache_disabled():
            for i in range(2):
                assert mock_session.get(MOCKED_URL).from_cache is False
    assert mock_session.get(MOCKED_URL).from_cache is True


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
    ],
)
def test_urls_expire_after(url, expected_expire_after):
    session = CachedSession(
        urls_expire_after={
            '*.site_1.com': 60 * 60,
            'site_2.com/resource_1': 60 * 60 * 2,
            'site_2.com/resource_2': 60 * 60 * 24,
            'site_2.com/static': -1,
        },
    )
    assert session._url_expire_after(url) == expected_expire_after


@pytest.mark.parametrize(
    'url, expected_expire_after',
    [
        ('https://img.site_1.com/image.jpeg', 60 * 60),
        ('https://img.site_1.com/resource/1', 60 * 60 * 2),
        ('https://site_2.com', 1),
        ('https://any_other_site.com', 1),
    ],
)
def test_urls_expire_after__evaluation_order(url, expected_expire_after):
    """If there are multiple matches, the first match should be used in the order defined"""
    session = CachedSession(
        urls_expire_after={
            '*.site_1.com/resource': 60 * 60 * 2,
            '*.site_1.com': 60 * 60,
            '*': 1,
        },
    )
    assert session._url_expire_after(url) == expected_expire_after


def test_get_expiration_precedence():
    session = CachedSession(expire_after=1, urls_expire_after={'*.site_1.com': 60 * 60})
    assert session._get_expiration() == 1
    assert session._get_expiration('site_2.com') == 1
    assert session._get_expiration('img.site_1.com/image.jpg') == 60 * 60
    with session.request_expire_after(30):
        assert session._get_expiration() == 30
        assert session._get_expiration('img.site_1.com/image.jpg') == 30


def test_remove_expired_responses(mock_session):
    unexpired_url = f'{MOCKED_URL}?x=1'
    mock_session.mock_adapter.register_uri('GET', unexpired_url, status_code=200, text='mock response')
    mock_session.expire_after = timedelta(seconds=0.2)
    mock_session.get(MOCKED_URL)
    mock_session.get(MOCKED_URL_JSON)
    time.sleep(0.2)
    mock_session.get(unexpired_url)

    # At this point we should have 1 unexpired response and 2 expired responses
    assert len(mock_session.cache.responses) == 3
    mock_session.remove_expired_responses()
    assert len(mock_session.cache.responses) == 1
    cached_response = list(mock_session.cache.responses.values())[0]
    assert cached_response.url == unexpired_url

    # Now the last response should be expired as well
    time.sleep(0.2)
    mock_session.remove_expired_responses()
    assert len(mock_session.cache.responses) == 0


def test_remove_expired_responses__error(mock_session):
    # Start with two cached responses, one of which will raise an error
    mock_session.get(MOCKED_URL)
    mock_session.get(MOCKED_URL_JSON)
    side_effects = [mock_session.get(MOCKED_URL_JSON), PickleError, PickleError]

    with patch.object(DbPickleDict, '__getitem__', side_effect=side_effects):
        mock_session.remove_expired_responses()
    assert len(mock_session.cache.responses) == 1
    assert mock_session.get(MOCKED_URL).from_cache is False
    assert mock_session.get(MOCKED_URL_JSON).from_cache is True


def test_remove_expired_responses__extend_expiration(mock_session):
    # Start with an expired response
    mock_session.expire_after = datetime.utcnow() - timedelta(seconds=0.01)
    mock_session.get(MOCKED_URL)

    # Set expiration in the future and revalidate
    mock_session.remove_expired_responses(expire_after=datetime.utcnow() + timedelta(seconds=1))
    assert len(mock_session.cache.responses) == 1
    response = mock_session.get(MOCKED_URL)
    assert response.is_expired is False and response.from_cache is True


def test_remove_expired_responses__shorten_expiration(mock_session):
    # Start with a non-expired response
    mock_session.expire_after = datetime.utcnow() + timedelta(seconds=1)
    mock_session.get(MOCKED_URL)

    # Set expiration in the past and revalidate
    mock_session.remove_expired_responses(expire_after=datetime.utcnow() - timedelta(seconds=0.01))
    assert len(mock_session.cache.responses) == 0
    response = mock_session.get(MOCKED_URL)
    assert response.is_expired is False and response.from_cache is False


def test_remove_expired_responses__per_request(mock_session):
    # Cache 3 responses with different expiration times
    second_url = f'{MOCKED_URL}/endpoint_2'
    third_url = f'{MOCKED_URL}/endpoint_3'
    mock_session.mock_adapter.register_uri('GET', second_url, status_code=200)
    mock_session.mock_adapter.register_uri('GET', third_url, status_code=200)
    mock_session.get(MOCKED_URL)
    mock_session.get(second_url, expire_after=0.2)
    mock_session.get(third_url, expire_after=0.4)

    # All 3 responses should still be cached
    mock_session.remove_expired_responses()
    assert len(mock_session.cache.responses) == 3

    # One should be expired after 0.2s, and another should be expired after 0.4s
    time.sleep(0.2)
    mock_session.remove_expired_responses()
    assert len(mock_session.cache.responses) == 2
    time.sleep(0.2)
    mock_session.remove_expired_responses()
    assert len(mock_session.cache.responses) == 1


def test_per_request__expiration(mock_session):
    """No per-session expiration is set, but then overridden with per-request expiration"""
    mock_session.expire_after = None
    response = mock_session.get(MOCKED_URL, expire_after=0.01)
    assert response.from_cache is False
    time.sleep(0.01)
    response = mock_session.get(MOCKED_URL)
    assert response.from_cache is False


def test_per_request__no_expiration(mock_session):
    """A per-session expiration is set, but then overridden with no per-request expiration"""
    mock_session.expire_after = 0.01
    response = mock_session.get(MOCKED_URL, expire_after=-1)
    assert response.from_cache is False
    time.sleep(0.01)
    response = mock_session.get(MOCKED_URL)
    assert response.from_cache is True


def test_unpickle_errors(mock_session):
    """If there is an error during deserialization, the request should be made again"""
    assert mock_session.get(MOCKED_URL_JSON).from_cache is False

    with patch.object(DbPickleDict, '__getitem__', side_effect=PickleError):
        resp = mock_session.get(MOCKED_URL_JSON)
        assert resp.from_cache is False
        assert resp.json()['message'] == 'mock json response'

    resp = mock_session.get(MOCKED_URL_JSON)
    assert resp.from_cache is True
    assert resp.json()['message'] == 'mock json response'


def test_cache_signing():
    # Without a secret key, plain pickle should be used
    session = CachedSession()
    assert session.cache.responses._serializer == pickle

    # With a secret key, itsdangerous should be used
    secret_key = str(uuid4())
    session = CachedSession(secret_key=secret_key)
    assert isinstance(session.cache.responses._serializer, Serializer)

    # Simple serialize/deserialize round trip
    session.cache.responses['key'] = 'value'
    assert session.cache.responses['key'] == 'value'

    # Without the same signing key, the item shouldn't be considered safe to deserialize
    session = CachedSession(secret_key='a different key')
    with pytest.raises(BadSignature):
        session.cache.responses['key']
