"""CachedSession tests that use mocked responses only"""
import json
import pickle
from collections import UserDict, defaultdict
from datetime import datetime, timedelta
from logging import getLogger
from pathlib import Path
from pickle import PickleError
from time import sleep, time
from unittest.mock import patch
from urllib.parse import urlencode

import pytest
import requests
from requests import HTTPError, Request, RequestException
from requests.structures import CaseInsensitiveDict

from requests_cache import ALL_METHODS, CachedSession
from requests_cache._utils import get_placeholder_class
from requests_cache.backends import BACKEND_CLASSES, BaseCache
from requests_cache.backends.base import DESERIALIZE_ERRORS
from requests_cache.policy.expiration import DO_NOT_CACHE, EXPIRE_IMMEDIATELY, NEVER_EXPIRE
from tests.conftest import (
    MOCKED_URL,
    MOCKED_URL_200_404,
    MOCKED_URL_404,
    MOCKED_URL_500,
    MOCKED_URL_ETAG,
    MOCKED_URL_HTTPS,
    MOCKED_URL_JSON,
    MOCKED_URL_REDIRECT,
    MOCKED_URL_REDIRECT_TARGET,
    MOCKED_URL_VARY,
    ignore_deprecation,
    patch_normalize_url,
)

logger = getLogger(__name__)

# Basic initialization
# -----------------------------------------------------


class MyCache(BaseCache):
    pass


def test_init_backend_instance():
    backend = MyCache()
    session = CachedSession(backend=backend)
    assert session.cache is backend


def test_init_unregistered_backend():
    with pytest.raises(ValueError):
        CachedSession(backend='nonexistent')


def test_init_cache_path_expansion():
    session = CachedSession('~', backend='filesystem')
    assert session.cache.cache_dir == Path("~").expanduser()


@patch.dict(BACKEND_CLASSES, {'mongodb': get_placeholder_class()})
def test_init_missing_backend_dependency():
    """Test that the correct error is thrown when a user does not have a dependency installed"""
    with pytest.raises(ImportError):
        CachedSession(backend='mongodb')


def test_repr(mock_session):
    """Test session and cache string representations"""
    mock_session.settings.expire_after = 11
    mock_session.settings.cache_control = True

    assert mock_session.cache.cache_name in repr(mock_session)
    assert 'expire_after=11' in repr(mock_session)
    assert 'cache_control=True' in repr(mock_session)


def test_pickle__disabled():
    with pytest.raises(NotImplementedError):
        pickle.dumps(CachedSession(backend='memory'))


def test_response_defaults(mock_session):
    """Both cached and new responses should always have the following attributes"""
    mock_session.settings.expire_after = datetime.utcnow() + timedelta(days=1)
    response_1 = mock_session.get(MOCKED_URL)
    response_2 = mock_session.get(MOCKED_URL)
    response_3 = mock_session.get(MOCKED_URL)
    cache_key = '29de1c4491126e0b'

    assert response_1.cache_key == cache_key
    assert isinstance(response_1.created_at, datetime)
    assert isinstance(response_1.expires, datetime)
    assert response_1.from_cache is False
    assert response_1.is_expired is False

    assert isinstance(response_2.created_at, datetime)
    assert isinstance(response_2.expires, datetime)
    assert response_2.cache_key == cache_key
    assert response_2.created_at == response_3.created_at
    assert response_2.expires == response_3.expires
    assert response_2.from_cache is response_3.from_cache is True
    assert response_2.is_expired is response_3.is_expired is False


# Main combinations of request methods and data fields
# -----------------------------------------------------


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
    mock_session.settings.ignored_parameters = ['ignored']
    mock_session.settings.match_headers = True
    params_1 = {'ignored': 'value_1', 'param': 'value_1'}
    params_2 = {'ignored': 'value_2', 'param': 'value_1'}
    params_3 = {'ignored': 'value_2', 'param': 'value_2'}

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
    mock_session.settings.ignored_parameters = ['ignored']
    params_1 = {'ignored': 'asdf', 'param': 'value_1'}

    mock_session.request(method, MOCKED_URL, **{field: params_1})
    cached_response = mock_session.request(method, MOCKED_URL, **{field: params_1})
    request_url = cached_response.request.url
    headers = cached_response.request.headers
    body = cached_response.request.body.decode('utf-8')

    assert 'ignored' not in cached_response.url or 'ignored=REDACTED' in cached_response.url
    assert 'ignored' not in request_url or 'ignored=REDACTED' in request_url
    assert 'ignored' not in headers or headers['ignored'] == 'REDACTED'
    if field == 'data':
        assert 'ignored=REDACTED' in body
    elif field == 'json':
        body = json.loads(body)
        assert body['ignored'] == 'REDACTED'


# Variations of relevant request arguments
# -----------------------------------------------------


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


# Request matching
# -----------------------------------------------------


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


def test_match_headers(mock_session):
    """With match_headers, requests with different headers should have different cache keys"""
    mock_session.settings.match_headers = True
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
    mock_session.settings.match_headers = True
    headers = {'Accept': 'application/json', 'Custom': 'abc'}
    reversed_headers = {'Custom': 'abc', 'Accept': 'application/json'}
    assert mock_session.get(MOCKED_URL, headers=headers).from_cache is False
    assert mock_session.get(MOCKED_URL, headers=reversed_headers).from_cache is True


def test_match_headers__list(mock_session):
    """match_headers can optionally be a list of specific headers to include"""
    mock_session.settings.match_headers = ['Accept']
    headers_1 = {'Accept': 'application/json', 'User-Agent': 'qutebrowser'}
    headers_2 = {'Accept': 'application/json', 'User-Agent': 'Firefox'}
    headers_3 = {'Accept': 'text/plain', 'User-Agent': 'qutebrowser'}

    assert mock_session.get(MOCKED_URL, headers=headers_1).from_cache is False
    assert mock_session.get(MOCKED_URL, headers=headers_1).from_cache is True
    assert mock_session.get(MOCKED_URL, headers=headers_2).from_cache is True
    assert mock_session.get(MOCKED_URL, headers=headers_3).from_cache is False


def test_match_headers__vary(mock_session):
    """Vary should be used to validate headers, if available.
    It should also override `match_headers` for the secondary cache key, if both are provided.
    """
    # mock_session.settings.match_headers = ['Accept-Encoding']
    headers_1 = {'Accept': 'application/json', 'User-Agent': 'qutebrowser'}
    headers_2 = {'Accept': 'application/json', 'User-Agent': 'Firefox'}
    headers_3 = {'Accept': 'text/plain', 'User-Agent': 'qutebrowser'}

    assert mock_session.get(MOCKED_URL_VARY, headers=headers_1).from_cache is False
    assert mock_session.get(MOCKED_URL_VARY, headers=headers_1).from_cache is True
    assert mock_session.get(MOCKED_URL_VARY, headers=headers_2).from_cache is True
    assert mock_session.get(MOCKED_URL_VARY, headers=headers_3).from_cache is False


def test_include_get_headers():
    """include_get_headers is aliased to match_headers for backwards-compatibility"""
    session = CachedSession(include_get_headers=True, backend='memory')
    assert session.settings.match_headers is True


# Error handling
# -----------------------------------------------------


@pytest.mark.parametrize('exception_cls', DESERIALIZE_ERRORS)
def test_cache_error(exception_cls, mock_session):
    """If there is an error while fetching a cached response, a new one should be fetched"""
    mock_session.get(MOCKED_URL)

    with patch.object(mock_session.cache.responses.serializer, 'loads', side_effect=exception_cls):
        assert mock_session.get(MOCKED_URL).from_cache is False


def test_expired_request_error(mock_session):
    """Without stale_if_error (default), if there is an error while re-fetching an expired
    response, the request should be re-raised
    """
    mock_session.settings.stale_if_error = False
    mock_session.settings.expire_after = 1
    mock_session.get(MOCKED_URL)
    sleep(1)

    with patch.object(mock_session.cache, 'save_response', side_effect=ValueError):
        with pytest.raises(ValueError):
            mock_session.get(MOCKED_URL)


def test_stale_if_error__exception(mock_session):
    """With stale_if_error, expect to get old cache data if there is an exception during a request"""
    mock_session.settings.stale_if_error = True
    mock_session.settings.expire_after = 1

    assert mock_session.get(MOCKED_URL).from_cache is False
    assert mock_session.get(MOCKED_URL).from_cache is True
    sleep(1)
    with patch.object(mock_session.cache, 'save_response', side_effect=RequestException):
        response = mock_session.get(MOCKED_URL)
        assert response.from_cache is True and response.is_expired is True


def test_stale_if_error__error_code(mock_session):
    """With stale_if_error, expect to get old cache data if a response has an error status code,
    that is not in allowable_codes.
    """
    mock_session.settings.stale_if_error = True
    mock_session.settings.expire_after = 1
    mock_session.settings.allowable_codes = (200,)

    assert mock_session.get(MOCKED_URL_200_404).status_code == 200

    sleep(1)

    response = mock_session.get(MOCKED_URL_200_404)
    assert response.status_code == 200
    assert response.from_cache is True
    assert response.is_expired is True


def test_stale_if_error__error_code_in_allowable_codes(mock_session):
    """With stale_if_error, expect to get the failed response if a response has an error status code,
    that is in allowable_codes.
    """
    mock_session.settings.stale_if_error = True
    mock_session.settings.expire_after = 1
    mock_session.settings.allowable_codes = (200, 404)

    assert mock_session.get(MOCKED_URL_200_404).status_code == 200

    sleep(1)

    response = mock_session.get(MOCKED_URL_200_404)
    assert response.status_code == 404
    assert response.from_cache is False
    assert response.is_expired is False


def test_stale_if_error__max_stale(mock_session):
    """With stale_if_error as a time value, expect to get old cache data if a response has an error
    status code AND it is expired by less than the specified time
    """
    mock_session.settings.stale_if_error = timedelta(seconds=15)
    mock_session.settings.expire_after = datetime.utcnow() - timedelta(seconds=10)
    mock_session.settings.allowable_codes = (200,)
    mock_session.get(MOCKED_URL_200_404).from_cache

    response = mock_session.get(MOCKED_URL_200_404)
    assert response.from_cache is True
    assert response.is_expired is True

    mock_session.settings.stale_if_error = 5
    with pytest.raises(HTTPError):
        mock_session.get(MOCKED_URL_200_404)


def test_old_data_on_error():
    """stale_if_error is aliased to old_data_on_error for backwards-compatibility"""
    session = CachedSession(old_data_on_error=True, backend='memory')
    assert session.settings.stale_if_error is True


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


def test_unpickle_errors(mock_session):
    """If there is an error during deserialization, the request should be made again"""
    assert mock_session.get(MOCKED_URL_JSON).from_cache is False

    with patch.object(mock_session.cache.responses.serializer, 'loads', side_effect=PickleError):
        resp = mock_session.get(MOCKED_URL_JSON)
        assert resp.from_cache is False
        assert resp.json()['message'] == 'mock json response'

    resp = mock_session.get(MOCKED_URL_JSON)
    assert resp.from_cache is True
    assert resp.json()['message'] == 'mock json response'


# Additional CachedSession settings and methods
# -----------------------------------------------------


def test_allowable_codes(mock_session):
    mock_session.settings.allowable_codes = (200, 404)

    # This request should be cached
    mock_session.get(MOCKED_URL_404)
    assert mock_session.cache.contains(url=MOCKED_URL_404)
    assert mock_session.get(MOCKED_URL_404).from_cache is True

    # This request should be filtered out on both read and write
    mock_session.get(MOCKED_URL_500)
    assert not mock_session.cache.contains(url=MOCKED_URL_500)
    assert mock_session.get(MOCKED_URL_500).from_cache is False


def test_allowable_methods(mock_session):
    mock_session.settings.allowable_methods = ['GET', 'OPTIONS']

    # This request should be cached
    mock_session.options(MOCKED_URL)
    assert mock_session.cache.contains(request=Request('OPTIONS', MOCKED_URL))
    assert mock_session.options(MOCKED_URL).from_cache is True

    # These requests should be filtered out on both read and write
    mock_session.put(MOCKED_URL)
    assert not mock_session.cache.contains(request=Request('PUT', MOCKED_URL))
    assert mock_session.put(MOCKED_URL).from_cache is False

    mock_session.patch(MOCKED_URL)
    assert not mock_session.cache.contains(request=Request('PATCH', MOCKED_URL))
    assert mock_session.patch(MOCKED_URL).from_cache is False

    mock_session.delete(MOCKED_URL)
    assert not mock_session.cache.contains(request=Request('DELETE', MOCKED_URL))
    assert mock_session.delete(MOCKED_URL).from_cache is False


def test_always_revalidate(mock_session):
    """The session always_revalidate option should send a conditional request, if possible"""
    mock_session.settings.expire_after = 60
    response_1 = mock_session.get(MOCKED_URL_ETAG)
    response_2 = mock_session.get(MOCKED_URL_ETAG)
    mock_session.mock_adapter.register_uri('GET', MOCKED_URL_ETAG, status_code=304)

    mock_session.settings.always_revalidate = True
    response_3 = mock_session.get(MOCKED_URL_ETAG)
    response_4 = mock_session.get(MOCKED_URL_ETAG)

    assert response_1.from_cache is False
    assert response_2.from_cache is True
    assert response_3.from_cache is True and response_3.revalidated is True
    assert response_4.from_cache is True and response_4.revalidated is True

    # Expect expiration to get reset after revalidation
    assert response_2.expires < response_4.expires


def test_default_ignored_parameters(mock_session):
    """Common auth params and headers (for OAuth2, etc.) should be ignored by default"""
    mock_session.get(
        MOCKED_URL,
        params={'access_token': 'token'},
        headers={'Authorization': 'Bearer token'},
    )
    response = mock_session.get(
        MOCKED_URL,
        params={'access_token': 'token'},
        headers={'Authorization': 'Bearer token'},
    )
    assert response.from_cache is True

    unauthenticated_response = mock_session.get(MOCKED_URL)
    assert unauthenticated_response.from_cache is False

    assert 'access_token=REDACTED' in response.url
    assert 'access_token=REDACTED' in response.request.url
    assert response.request.headers['Authorization'] == 'REDACTED'


@patch_normalize_url
def test_filter_fn(mock_normalize_url, mock_session):
    mock_session.settings.filter_fn = lambda r: r.request.url != MOCKED_URL_JSON

    # This request should be cached
    mock_session.get(MOCKED_URL)
    assert mock_session.cache.contains(url=MOCKED_URL)
    assert mock_session.get(MOCKED_URL).from_cache is True

    # This request should be filtered out on both read and write
    mock_session.get(MOCKED_URL_JSON)
    assert not mock_session.cache.contains(url=MOCKED_URL_JSON)
    assert mock_session.get(MOCKED_URL_JSON).from_cache is False


@patch_normalize_url
def test_filter_fn__retroactive(mock_normalize_url, mock_session):
    """filter_fn should also apply to previously cached responses"""
    mock_session.get(MOCKED_URL_JSON)
    mock_session.settings.filter_fn = lambda r: r.request.url != MOCKED_URL_JSON
    mock_session.get(MOCKED_URL_JSON)
    assert not mock_session.cache.contains(url=MOCKED_URL_JSON)


def test_key_fn(mock_session):
    def create_custom_key(request, **kwargs):
        """Create a key based on only the request URL (without params)"""
        return request.url.split('?')[0]

    mock_session.settings.key_fn = create_custom_key
    mock_session.get(MOCKED_URL)
    response = mock_session.get(MOCKED_URL, params={'k': 'v'})
    assert response.from_cache is True


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


def test_expire_after_alias(mock_session):
    """CachedSession has an `expire_after` property for backwards-compatibility"""
    mock_session.expire_after = 60
    assert mock_session.expire_after == mock_session.settings.expire_after == 60


def test_do_not_cache(mock_session):
    """DO_NOT_CACHE should bypass the cache on both read and write"""
    mock_session.get(MOCKED_URL)
    assert mock_session.cache.contains(url=MOCKED_URL)

    # Skip read
    response = mock_session.get(MOCKED_URL, expire_after=DO_NOT_CACHE)
    assert response.from_cache is False

    # Skip write
    mock_session.settings.expire_after = DO_NOT_CACHE
    mock_session.get(MOCKED_URL_JSON)
    assert not mock_session.cache.contains(url=MOCKED_URL_JSON)


def test_expire_immediately(mock_session):
    """EXPIRE_IMMEDIATELY should save a response only if it has a validator"""
    # Without validator
    mock_session.settings.expire_after = EXPIRE_IMMEDIATELY
    mock_session.get(MOCKED_URL)
    response = mock_session.get(MOCKED_URL)
    assert not mock_session.cache.contains(url=MOCKED_URL)
    assert response.from_cache is False

    # With validator
    mock_session.get(MOCKED_URL_ETAG)
    response = mock_session.get(MOCKED_URL_ETAG)


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
        mock_session.settings.expire_after = datetime.utcnow() - timedelta(1)
    if cache_hit:
        mock_session.mock_adapter.register_uri('GET', url, status_code=200)
        mock_session.get(url)
    mock_session.mock_adapter.register_uri('GET', url, status_code=response_code)

    response = mock_session.get(url)
    assert response.from_cache is expected_from_cache


def test_url_allowlist(mock_session):
    """If the default is 0, only URLs matching patterns in urls_expire_after should be cached"""
    mock_session.settings.urls_expire_after = {
        MOCKED_URL_JSON: 60,
        '*': DO_NOT_CACHE,
    }
    mock_session.get(MOCKED_URL_JSON)
    assert mock_session.get(MOCKED_URL_JSON).from_cache is True
    mock_session.get(MOCKED_URL)
    assert mock_session.get(MOCKED_URL).from_cache is False
    assert not mock_session.cache.contains(url=MOCKED_URL)


def test_invalid_expiration(mock_session):
    mock_session.settings.expire_after = 'tomorrow'
    with pytest.raises(ValueError):
        mock_session.get(MOCKED_URL)

    mock_session.settings.expire_after = object()
    with pytest.raises(TypeError):
        mock_session.get(MOCKED_URL)

    mock_session.settings.expire_after = None
    mock_session.settings.urls_expire_after = {'*': 'tomorrow'}
    with pytest.raises(ValueError):
        mock_session.get(MOCKED_URL)


def test_stale_while_revalidate(mock_session):
    # Start with expired responses
    mocked_url_2 = f'{MOCKED_URL_ETAG}?k=v'
    mock_session.settings.stale_while_revalidate = True
    mock_session.get(MOCKED_URL_ETAG, expire_after=timedelta(seconds=-2))
    mock_session.get(mocked_url_2, expire_after=timedelta(seconds=-2))
    assert mock_session.cache.contains(url=MOCKED_URL_ETAG)

    # First, check that the correct method is called
    mock_session.mock_adapter.register_uri('GET', MOCKED_URL_ETAG, status_code=304)
    with patch.object(CachedSession, '_resend_async') as mock_send:
        response = mock_session.get(MOCKED_URL_ETAG)
        mock_send.assert_called_once()

    def slow_request(*args, **kwargs):
        sleep(0.1)
        return mock_session._send_and_cache(*args, **kwargs)

    # Next, test that the revalidation request is non-blocking
    start = time()
    with patch.object(CachedSession, '_send_and_cache', side_effect=slow_request) as mock_send:
        response = mock_session.get(mocked_url_2, expire_after=60)
        assert response.from_cache is True and response.is_expired is True
        assert time() - start < 0.1  # Response should be returned immediately; request takes 0.1s
        sleep(1)  # Background thread may be slow on CI runner
        mock_send.assert_called()

    # An extra sleep AFTER patching magically fixes this test on pypy, and I have no idea why
    sleep(1)

    # Finally, check that the cached response has been refreshed
    response = mock_session.get(mocked_url_2)
    assert response.from_cache is True and response.is_expired is False


def test_stale_while_revalidate__time(mock_session):
    """stale_while_revalidate should also accept a time value (max acceptable staleness)"""
    mocked_url_2 = f'{MOCKED_URL_ETAG}?k=v'
    mock_session.settings.stale_while_revalidate = timedelta(seconds=3)
    mock_session.get(MOCKED_URL_ETAG, expire_after=timedelta(seconds=-2))
    response = mock_session.get(mocked_url_2, expire_after=timedelta(seconds=-4))

    # stale_while_revalidate should apply to this response (expired 2 seconds ago)
    response = mock_session.get(MOCKED_URL_ETAG)
    assert response.from_cache is True and response.is_expired is True

    # but not this response (expired 4 seconds ago)
    response = mock_session.get(mocked_url_2)
    assert response.from_cache is False and response.is_expired is False


def test_stale_while_revalidate__refresh(mock_session):
    """stale_while_revalidate should also apply to normal refresh requests"""
    mock_session.settings.stale_while_revalidate = True
    mock_session.get(MOCKED_URL, expire_after=1)
    sleep(1)  # An expired response without a validator won't be cached, so need to sleep

    response = mock_session.get(MOCKED_URL)
    assert response.from_cache is True and response.is_expired is True

    sleep(0.2)
    response = mock_session.get(MOCKED_URL)
    assert response.from_cache is True and response.is_expired is False


# Additional request() and send() options
# -----------------------------------------------------


def test_request_expire_after__enable_expiration(mock_session):
    """No per-session expiration is set, but then overridden for a single request"""
    mock_session.settings.expire_after = None
    response = mock_session.get(MOCKED_URL, expire_after=1)
    assert response.from_cache is False
    assert mock_session.get(MOCKED_URL).from_cache is True

    sleep(1)
    response = mock_session.get(MOCKED_URL)
    assert response.from_cache is False


def test_request_expire_after__disable_expiration(mock_session):
    """A per-session expiration is set, but then disabled for a single request"""
    mock_session.settings.expire_after = 60
    response = mock_session.get(MOCKED_URL, expire_after=NEVER_EXPIRE)
    response = mock_session.get(MOCKED_URL, expire_after=NEVER_EXPIRE)
    assert response.from_cache is True
    assert response.expires is None


def test_request_expire_after__prepared_request(mock_session):
    """Pre-request expiration should also work for PreparedRequests with CachedSession.send()"""
    mock_session.settings.expire_after = None
    request = Request('GET', MOCKED_URL, headers={}, data=None).prepare()
    response = mock_session.send(request, expire_after=1)
    assert response.from_cache is False
    assert mock_session.send(request).from_cache is True

    sleep(1)
    response = mock_session.get(MOCKED_URL)
    assert response.from_cache is False


def test_request_only_if_cached__cached(mock_session):
    """only_if_cached has no effect if the response is already cached"""
    mock_session.get(MOCKED_URL)
    response = mock_session.get(MOCKED_URL, only_if_cached=True)
    assert response.from_cache is True
    assert response.is_expired is False


def test_request_only_if_cached__uncached(mock_session):
    """only_if_cached should return a 504 response if it is not already cached"""
    response = mock_session.get(MOCKED_URL, only_if_cached=True)
    assert response.status_code == 504
    with pytest.raises(HTTPError):
        response.raise_for_status()


def test_request_only_if_cached__expired(mock_session):
    """By default, only_if_cached will not return an expired response"""
    mock_session.get(MOCKED_URL, expire_after=1)
    sleep(1)

    response = mock_session.get(MOCKED_URL, only_if_cached=True)
    assert response.status_code == 504


def test_request_only_if_cached__stale_if_error__expired(mock_session):
    """only_if_cached *will* return an expired response if stale_if_error is also set"""
    mock_session.get(MOCKED_URL, expire_after=1)
    sleep(1)

    mock_session.settings.stale_if_error = True
    response = mock_session.get(MOCKED_URL, only_if_cached=True)
    assert response.status_code == 200
    assert response.from_cache is True
    assert response.is_expired is True


def test_request_only_if_cached__skips_revalidate(mock_session):
    """only_if_cached should skip other revalidation conditions if the response isn't expired.
    This includes taking precedence over refresh=True.
    """
    mock_session.get(MOCKED_URL)
    response = mock_session.get(MOCKED_URL, only_if_cached=True, refresh=True)
    assert response.from_cache is True
    assert response.is_expired is False


def test_request_only_if_cached__prepared_request(mock_session):
    """The only_if_cached option should also work for PreparedRequests with CachedSession.send()"""
    request = Request('GET', MOCKED_URL, headers={}).prepare()
    response = mock_session.send(request, only_if_cached=True)
    assert response.status_code == 504
    with pytest.raises(HTTPError):
        response.raise_for_status()


def test_request_refresh(mock_session):
    """The refresh option should send a conditional request, if possible"""
    response_1 = mock_session.get(MOCKED_URL_ETAG, expire_after=60)
    response_2 = mock_session.get(MOCKED_URL_ETAG)
    mock_session.mock_adapter.register_uri('GET', MOCKED_URL_ETAG, status_code=304)

    response_3 = mock_session.get(MOCKED_URL_ETAG, refresh=True, expire_after=60)
    response_4 = mock_session.get(MOCKED_URL_ETAG)

    assert response_1.from_cache is False
    assert response_2.from_cache is True
    assert response_3.from_cache is True and response_3.revalidated is True
    assert response_4.from_cache is True and response_4.revalidated is False

    # Expect expiration to get reset after revalidation
    assert response_2.expires < response_4.expires


def test_request_refresh__no_validator(mock_session):
    """The refresh option should result in a new (unconditional) request if the cached response has
    no validator
    """
    response_1 = mock_session.get(MOCKED_URL, expire_after=60)
    response_2 = mock_session.get(MOCKED_URL)
    mock_session.mock_adapter.register_uri('GET', MOCKED_URL, status_code=304)

    response_3 = mock_session.get(MOCKED_URL, refresh=True, expire_after=60)
    response_4 = mock_session.get(MOCKED_URL)

    assert response_1.from_cache is False
    assert response_2.from_cache is True
    assert response_3.from_cache is True and response_3.revalidated is False
    assert response_2.expires == response_4.expires


def test_request_refresh__prepared_request(mock_session):
    """The refresh option should also work for PreparedRequests with CachedSession.send()"""
    mock_session.settings.expire_after = 60
    request = Request('GET', MOCKED_URL_ETAG, headers={}, data=None).prepare()
    response_1 = mock_session.send(request)
    response_2 = mock_session.send(request)
    mock_session.mock_adapter.register_uri('GET', MOCKED_URL_ETAG, status_code=304)

    response_3 = mock_session.send(request, refresh=True)
    response_4 = mock_session.send(request)

    assert response_1.from_cache is False
    assert response_2.from_cache is True
    assert response_3.from_cache is True

    # Expect expiration to get reset after revalidation
    assert response_2.expires < response_4.expires


def test_request_force_refresh(mock_session):
    """The force_refresh option should send and cache a new request. Any expire_after value provided
    should overwrite the previous value."""
    response_1 = mock_session.get(MOCKED_URL, expire_after=NEVER_EXPIRE)
    response_2 = mock_session.get(MOCKED_URL, expire_after=360, force_refresh=True)
    response_3 = mock_session.get(MOCKED_URL)

    assert response_1.from_cache is False
    assert response_2.from_cache is False
    assert response_3.from_cache is True
    assert response_3.expires is not None


def test_request_force_refresh__prepared_request(mock_session):
    """The force_refresh option should also work for PreparedRequests with CachedSession.send()"""
    mock_session.settings.expire_after = 60
    request = Request('GET', MOCKED_URL, headers={}, data=None)
    response_1 = mock_session.send(request.prepare())
    response_2 = mock_session.send(request.prepare(), force_refresh=True)
    response_3 = mock_session.send(request.prepare())

    assert response_1.from_cache is False
    assert response_2.from_cache is False
    assert response_3.from_cache is True
    assert response_3.expires is not None


# Deprecated methods
# --------------------


def test_remove_expired_responses(mock_session):
    with ignore_deprecation(), patch.object(mock_session.cache, 'delete') as mock_delete:
        mock_session.remove_expired_responses()
        mock_delete.assert_called_once_with(expired=True, invalid=True)
