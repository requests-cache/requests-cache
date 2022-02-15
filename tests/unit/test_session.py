"""CachedSession + BaseCache tests that use mocked responses only"""
# TODO: This could be split up into some smaller test modules
import json
import time
from collections import UserDict, defaultdict
from datetime import datetime, timedelta
from pickle import PickleError
from unittest.mock import patch
from urllib.parse import urlencode

import pytest
import requests
from requests import Request, RequestException
from requests.structures import CaseInsensitiveDict

from requests_cache import ALL_METHODS, CachedResponse, CachedSession
from requests_cache._utils import get_placeholder_class
from requests_cache.backends import BACKEND_CLASSES, BaseCache, SQLiteDict, SQLitePickleDict
from requests_cache.backends.base import DESERIALIZE_ERRORS
from requests_cache.cache_keys import create_key
from tests.conftest import (
    MOCKED_URL,
    MOCKED_URL_404,
    MOCKED_URL_HTTPS,
    MOCKED_URL_JSON,
    MOCKED_URL_REDIRECT,
    MOCKED_URL_REDIRECT_TARGET,
)

YESTERDAY = datetime.utcnow() - timedelta(days=1)


def test_init_unregistered_backend():
    with pytest.raises(ValueError):
        CachedSession(backend='nonexistent')


@patch.dict(BACKEND_CLASSES, {'mongo': get_placeholder_class()})
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


def test_init_backend_instance__kwargs():
    backend = MyCache()
    session = CachedSession(
        'test_cache',
        backend=backend,
        ignored_parameters=['foo'],
        include_get_headers=True,
    )

    assert session.cache.cache_name == 'test_cache'
    assert session.cache.ignored_parameters == ['foo']
    assert session.cache.match_headers is True


def test_init_backend_class():
    session = CachedSession('test_cache', backend=MyCache)
    assert isinstance(session.cache, MyCache)
    assert session.cache.cache_name == 'test_cache'


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
@pytest.mark.parametrize('field', ['params', 'headers', 'data', 'json'])
def test_all_methods__ignored_parameters__not_matched(field, method, mock_session):
    """Test all relevant combinations of methods and data fields. Requests with different request
    params, data, or json should not be cached under different keys based on an ignored param.
    """
    mock_session.cache.ignored_parameters = ['ignored']
    mock_session.cache.match_headers = True
    params_1 = {'ignored': 'value_1', 'not_ignored': 'value_1'}
    params_2 = {'ignored': 'value_2', 'not_ignored': 'value_1'}
    params_3 = {'ignored': 'value_2', 'not_ignored': 'value_2'}

    assert mock_session.request(method, MOCKED_URL, **{field: params_1}).from_cache is False
    assert mock_session.request(method, MOCKED_URL, **{field: params_1}).from_cache is True
    assert mock_session.request(method, MOCKED_URL, **{field: params_2}).from_cache is True
    mock_session.request(method, MOCKED_URL, params={'a': 'b'})
    assert mock_session.request(method, MOCKED_URL, **{field: params_3}).from_cache is False


@pytest.mark.parametrize('method', ALL_METHODS)
@pytest.mark.parametrize('field', ['params', 'headers', 'data', 'json'])
def test_all_methods__ignored_parameters__redacted(field, method, mock_session):
    """Test all relevant combinations of methods and data fields. Requests with ignored params
    should have those values redacted from the cached response.
    """
    mock_session.cache.ignored_parameters = ['access_token']
    params_1 = {'access_token': 'asdf', 'not_ignored': 'value_1'}

    mock_session.request(method, MOCKED_URL, **{field: params_1})
    cached_response = mock_session.request(method, MOCKED_URL, **{field: params_1})
    assert 'access_token' not in cached_response.url
    assert 'access_token' not in cached_response.request.url
    assert 'access_token' not in cached_response.request.headers
    assert 'access_token' not in cached_response.request.body.decode('utf-8')


def test_params_positional_arg(mock_session):
    mock_session.request('GET', MOCKED_URL, {'param_1': 1})
    response = mock_session.request('GET', MOCKED_URL, {'param_1': 1})
    assert 'param_1=1' in response.url


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


def test_repr(mock_session):
    """Test session and cache string representations"""
    mock_session.expire_after = 11
    mock_session.cache.responses['key'] = 'value'
    mock_session.cache.redirects['key'] = 'value'
    mock_session.cache.redirects['key_2'] = 'value'

    assert mock_session.cache.cache_name in repr(mock_session) and '11' in repr(mock_session)
    assert '2 redirects' in str(mock_session.cache) and '1 responses' in str(mock_session.cache)


def test_urls(mock_session):
    for url in [MOCKED_URL, MOCKED_URL_JSON, MOCKED_URL_HTTPS]:
        mock_session.get(url)

    expected_urls = [MOCKED_URL, MOCKED_URL_JSON, MOCKED_URL_HTTPS]
    assert set(mock_session.cache.urls) == set(expected_urls)


def test_urls__with_invalid_response(mock_session):
    responses = [mock_session.get(url) for url in [MOCKED_URL, MOCKED_URL_JSON, MOCKED_URL_HTTPS]]
    responses[2] = AttributeError
    with patch.object(SQLitePickleDict, '__getitem__', side_effect=responses):
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

    with patch.object(SQLitePickleDict, '__getitem__', side_effect=responses):
        values = mock_session.cache.values(check_expiry=check_expiry)
        assert len(list(values)) == expected_count

    # The invalid response should be skipped, but remain in the cache for now
    assert len(mock_session.cache.responses.keys()) == 3


class TimeBomb:
    """Class that will raise an error when unpickled"""

    def __init__(self):
        self.foo = 'bar'

    def __setstate__(self, value):
        raise ValueError('Invalid response!')


@pytest.mark.parametrize('check_expiry, expected_count', [(True, 2), (False, 3)])
def test_response_count(check_expiry, expected_count, mock_session):
    """response_count() should always exclude invalid responses, and optionally exclude expired responses"""
    mock_session.get(MOCKED_URL)
    mock_session.get(MOCKED_URL_JSON)

    mock_session.cache.responses['expired_response'] = CachedResponse(expires=YESTERDAY)
    mock_session.cache.responses['invalid_response'] = TimeBomb()
    assert mock_session.cache.response_count(check_expiry=check_expiry) == expected_count


def test_filter_fn(mock_session):
    mock_session.filter_fn = lambda r: r.request.url != MOCKED_URL_JSON
    mock_session.get(MOCKED_URL)
    mock_session.get(MOCKED_URL_JSON)

    assert mock_session.cache.has_url(MOCKED_URL)
    assert not mock_session.cache.has_url(MOCKED_URL_JSON)


def test_filter_fn__retroactive(mock_session):
    """filter_fn should also apply to previously cached responses"""
    mock_session.get(MOCKED_URL_JSON)
    mock_session.filter_fn = lambda r: r.request.url != MOCKED_URL_JSON
    mock_session.get(MOCKED_URL_JSON)

    assert not mock_session.cache.has_url(MOCKED_URL_JSON)


# def test_key_fn(mock_session):
#     def create_key(request, **kwargs):
#         """Create a key based on only the request URL (without params)"""
#         return request.url.split('?')[0]

#     mock_session.cache.key_fn = create_key
#     mock_session.get(MOCKED_URL)
#     response = mock_session.get(MOCKED_URL, params={'k': 'v'})
#     assert response.from_cache is True


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
    assert (
        mock_session.request(method, MOCKED_URL, data='{"data": "new raw data"}').from_cache
        is False
    )


@pytest.mark.parametrize('field', ['params', 'data', 'json'])
def test_normalize_params(field, mock_session):
    """Test normalization with different combinations of data fields"""
    params = {"a": "a", "b": ["1", "2", "3"], "c": "4"}
    reversed_params = dict(sorted(params.items(), reverse=True))

    assert mock_session.get(MOCKED_URL, **{field: params}).from_cache is False
    assert mock_session.get(MOCKED_URL, **{field: params}).from_cache is True
    assert mock_session.post(MOCKED_URL, **{field: params}).from_cache is False
    assert mock_session.post(MOCKED_URL, **{field: params}).from_cache is True
    assert mock_session.post(MOCKED_URL, **{field: reversed_params}).from_cache is True
    assert mock_session.post(MOCKED_URL, **{field: {"a": "b"}}).from_cache is False


@pytest.mark.parametrize('mapping_class', [dict, UserDict, CaseInsensitiveDict])
def test_normalize_params__custom_dicts(mapping_class, mock_session):
    """Test normalization with different dict-like classes"""
    params = {"a": "a", "b": ["1", "2", "3"], "c": "4"}
    params = mapping_class(params.items())

    assert mock_session.get(MOCKED_URL, params=params).from_cache is False
    assert mock_session.get(MOCKED_URL, params=params).from_cache is True
    assert mock_session.post(MOCKED_URL, params=params).from_cache is False
    assert mock_session.post(MOCKED_URL, params=params).from_cache is True


def test_normalize_params__serialized_body(mock_session):
    """Test normalization for serialized request body content"""
    headers = {'Content-Type': 'application/json'}
    params = {"a": "a", "b": ["1", "2", "3"], "c": "4"}
    sorted_params = json.dumps(params)
    reversed_params = json.dumps(dict(sorted(params.items(), reverse=True)))

    assert mock_session.post(MOCKED_URL, headers=headers, data=sorted_params).from_cache is False
    assert mock_session.post(MOCKED_URL, headers=headers, data=sorted_params).from_cache is True
    assert mock_session.post(MOCKED_URL, headers=headers, data=reversed_params).from_cache is True


def test_normalize_params__urlencoded_body(mock_session):
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    params = urlencode({"a": "a", "b": "!@#$%^&*()[]", "c": "4"})

    assert mock_session.post(MOCKED_URL, headers=headers, data=params).from_cache is False
    assert mock_session.post(MOCKED_URL, headers=headers, data=params).from_cache is True
    assert mock_session.post(MOCKED_URL, headers=headers, data=params).from_cache is True


def test_normalize_params__non_json_body(mock_session):
    """For serialized request body content that isn't in JSON format, no normalization is expected"""
    assert mock_session.post(MOCKED_URL, data=b'key_1=value_1,key_2=value_2').from_cache is False
    assert mock_session.post(MOCKED_URL, data=b'key_1=value_1,key_2=value_2').from_cache is True
    assert mock_session.post(MOCKED_URL, data=b'key_2=value_2,key_1=value_1').from_cache is False


def test_normalize_params__url(mock_session):
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


def test_response_defaults(mock_session):
    """Both cached and new responses should always have the following attributes"""
    mock_session.expire_after = datetime.utcnow() + timedelta(days=1)
    response_1 = mock_session.get(MOCKED_URL)
    response_2 = mock_session.get(MOCKED_URL)
    response_3 = mock_session.get(MOCKED_URL)
    cache_key = 'd7fa9fb7317b7412'

    assert response_1.cache_key == cache_key
    assert response_1.created_at is None
    assert response_1.expires is None
    assert response_1.from_cache is False
    assert response_1.is_expired is False

    assert isinstance(response_2.created_at, datetime)
    assert isinstance(response_2.expires, datetime)
    assert response_2.cache_key == cache_key
    assert response_2.created_at == response_3.created_at
    assert response_2.expires == response_3.expires
    assert response_2.from_cache is response_3.from_cache is True
    assert response_2.is_expired is response_3.is_expired is False


def test_match_headers(mock_session):
    """With match_headers, requests with different headers should have different cache keys"""
    mock_session.cache.match_headers = True
    headers_list = [
        {'Accept': 'application/json'},
        {'Accept': 'text/xml'},
        {'Accept': 'custom'},
        None,
    ]
    for headers in headers_list:
        assert mock_session.get(MOCKED_URL, headers=headers).from_cache is False
        assert mock_session.get(MOCKED_URL, headers=headers).from_cache is True


def test_match_headers__normalize(mock_session):
    """With match_headers, the same headers (in any order) should have the same cache key"""
    mock_session.cache.match_headers = True
    headers = {'Accept': 'application/json', 'Custom': 'abc'}
    reversed_headers = {'Custom': 'abc', 'Accept': 'application/json'}
    assert mock_session.get(MOCKED_URL, headers=headers).from_cache is False
    assert mock_session.get(MOCKED_URL, headers=reversed_headers).from_cache is True


def test_match_headers__list(mock_session):
    """match_headers can optionally be a list of specific headers to include"""
    mock_session.cache.match_headers = ['Accept']
    headers_1 = {'Accept': 'application/json', 'User-Agent': 'qutebrowser'}
    headers_2 = {'Accept': 'application/json', 'User-Agent': 'Firefox'}
    headers_3 = {'Accept': 'text/plain', 'User-Agent': 'qutebrowser'}

    assert mock_session.get(MOCKED_URL, headers=headers_1).from_cache is False
    assert mock_session.get(MOCKED_URL, headers=headers_1).from_cache is True
    assert mock_session.get(MOCKED_URL, headers=headers_2).from_cache is True
    assert mock_session.get(MOCKED_URL, headers=headers_3).from_cache is False


def test_include_get_headers():
    """include_get_headers is aliased to match_headers for backwards-compatibility"""
    session = CachedSession(include_get_headers=True, backend='memory')
    assert session.cache.match_headers is True


@pytest.mark.parametrize('exception_cls', DESERIALIZE_ERRORS)
def test_cache_error(exception_cls, mock_session):
    """If there is an error while fetching a cached response, a new one should be fetched"""
    mock_session.get(MOCKED_URL)
    with patch.object(SQLiteDict, '__getitem__', side_effect=exception_cls):
        assert mock_session.get(MOCKED_URL).from_cache is False


def test_expired_request_error(mock_session):
    """Without stale_if_error (default), if there is an error while re-fetching an expired
    response, the request should be re-raised and the expired item deleted"""
    mock_session.stale_if_error = False
    mock_session.expire_after = 1
    mock_session.get(MOCKED_URL)
    time.sleep(1)

    with patch.object(mock_session.cache, 'save_response', side_effect=ValueError):
        with pytest.raises(ValueError):
            mock_session.get(MOCKED_URL)
    assert len(mock_session.cache.responses) == 0


def test_stale_if_error__exception(mock_session):
    """With stale_if_error, expect to get old cache data if there is an exception during a request"""
    mock_session.stale_if_error = True
    mock_session.expire_after = 1

    assert mock_session.get(MOCKED_URL).from_cache is False
    assert mock_session.get(MOCKED_URL).from_cache is True
    time.sleep(1)
    with patch.object(mock_session.cache, 'save_response', side_effect=RequestException):
        response = mock_session.get(MOCKED_URL)
        assert response.from_cache is True and response.is_expired is True


def test_stale_if_error__error_code(mock_session):
    """With stale_if_error, expect to get old cache data if a response has an error status code"""
    mock_session.stale_if_error = True
    mock_session.expire_after = 1
    mock_session.allowable_codes = (200, 404)

    assert mock_session.get(MOCKED_URL_404).from_cache is False

    time.sleep(1)
    response = mock_session.get(MOCKED_URL_404)
    assert response.from_cache is True and response.is_expired is True


def test_old_data_on_error():
    """stale_if_error is aliased to old_data_on_error for backwards-compatibility"""
    session = CachedSession(old_data_on_error=True, backend='memory')
    assert session.stale_if_error is True


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


def test_do_not_cache(mock_session):
    """expire_after=0 should bypass the cache on both read and write"""
    # Bypass read
    mock_session.get(MOCKED_URL)
    assert mock_session.cache.has_url(MOCKED_URL)
    assert mock_session.get(MOCKED_URL, expire_after=0).from_cache is False

    # Bypass write
    mock_session.expire_after = 0
    mock_session.get(MOCKED_URL_JSON)
    assert not mock_session.cache.has_url(MOCKED_URL_JSON)


@pytest.mark.parametrize(
    'response_code, cache_hit, cache_expired, expected_from_cache',
    [
        # For 200 responses, never return stale cache data
        (200, False, False, False),
        (200, True, False, True),
        (200, True, True, False),
        # For 304 responses, return stale cache data
        (304, False, False, False),
        (304, True, False, True),
        (304, True, True, True),
    ],
)
def test_304_not_modified(
    response_code, cache_hit, cache_expired, expected_from_cache, mock_session
):
    url = f'{MOCKED_URL}/endpoint_2'
    if cache_expired:
        mock_session.expire_after = datetime.now() - timedelta(1)
    if cache_hit:
        mock_session.mock_adapter.register_uri('GET', url, status_code=200)
        mock_session.get(url)
    mock_session.mock_adapter.register_uri('GET', url, status_code=response_code)

    response = mock_session.get(url)
    assert response.from_cache is expected_from_cache


def test_url_allowlist(mock_session):
    """If the default is 0, only URLs matching patterns in urls_expire_after should be cached"""
    mock_session.urls_expire_after = {
        MOCKED_URL_JSON: 60,
        '*': 0,
    }
    mock_session.get(MOCKED_URL_JSON)
    assert mock_session.get(MOCKED_URL_JSON).from_cache is True
    mock_session.get(MOCKED_URL)
    assert mock_session.get(MOCKED_URL).from_cache is False


def test_remove_expired_responses(mock_session):
    unexpired_url = f'{MOCKED_URL}?x=1'
    mock_session.mock_adapter.register_uri(
        'GET', unexpired_url, status_code=200, text='mock response'
    )
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

    def error_on_key(key):
        if key == create_key(method='GET', url=MOCKED_URL_JSON):
            raise PickleError
        return mock_session.get(MOCKED_URL_JSON)

    with patch.object(SQLitePickleDict, '__getitem__', side_effect=error_on_key):
        mock_session.remove_expired_responses()
    assert len(mock_session.cache.responses) == 1
    assert mock_session.get(MOCKED_URL).from_cache is True
    assert mock_session.get(MOCKED_URL_JSON).from_cache is False


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
    mock_session.get(second_url, expire_after=1)
    mock_session.get(third_url, expire_after=2)

    # All 3 responses should still be cached
    mock_session.remove_expired_responses()
    for response in mock_session.cache.responses.values():
        print('Expires:', response.expires - datetime.utcnow() if response.expires else None)
    assert len(mock_session.cache.responses) == 3

    # One should be expired after 1s, and another should be expired after 2s
    time.sleep(1)
    mock_session.remove_expired_responses()
    assert len(mock_session.cache.responses) == 2
    time.sleep(2)
    mock_session.remove_expired_responses()
    assert len(mock_session.cache.responses) == 1


def test_per_request__enable_expiration(mock_session):
    """No per-session expiration is set, but then overridden for a single request"""
    mock_session.expire_after = None
    response = mock_session.get(MOCKED_URL, expire_after=1)
    assert response.from_cache is False
    assert mock_session.get(MOCKED_URL).from_cache is True

    time.sleep(1)
    response = mock_session.get(MOCKED_URL)
    assert response.from_cache is False


def test_per_request__disable_expiration(mock_session):
    """A per-session expiration is set, but then disabled for a single request"""
    mock_session.expire_after = 60
    response = mock_session.get(MOCKED_URL, expire_after=-1)
    response = mock_session.get(MOCKED_URL, expire_after=-1)
    assert response.from_cache is True
    assert response.expires is None


def test_per_request__prepared_request(mock_session):
    """The same should work for PreparedRequests with CachedSession.send()"""
    mock_session.expire_after = None
    request = Request(method='GET', url=MOCKED_URL, headers={}, data=None).prepare()
    response = mock_session.send(request, expire_after=1)
    assert response.from_cache is False
    assert mock_session.send(request).from_cache is True

    time.sleep(1)
    response = mock_session.get(MOCKED_URL)
    assert response.from_cache is False


def test_per_request__no_expiration(mock_session):
    """A per-session expiration is set, but then overridden with no per-request expiration"""
    mock_session.expire_after = 1
    response = mock_session.get(MOCKED_URL, expire_after=-1)
    assert response.from_cache is False
    assert response.expires is None


def test_unpickle_errors(mock_session):
    """If there is an error during deserialization, the request should be made again"""
    assert mock_session.get(MOCKED_URL_JSON).from_cache is False

    with patch.object(SQLitePickleDict, '__getitem__', side_effect=PickleError):
        resp = mock_session.get(MOCKED_URL_JSON)
        assert resp.from_cache is False
        assert resp.json()['message'] == 'mock json response'

    resp = mock_session.get(MOCKED_URL_JSON)
    assert resp.from_cache is True
    assert resp.json()['message'] == 'mock json response'
