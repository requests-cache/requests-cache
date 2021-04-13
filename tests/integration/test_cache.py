"""CachedSession tests that hit a containerized httpbin service"""
import json
import pytest

from tests.conftest import USE_PYTEST_HTTPBIN, httpbin

HTTPBIN_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
HTTPBIN_FORMATS = [
    'brotli',
    'deflate',
    'deny',
    'encoding/utf8',
    'gzip',
    'html',
    'image/jpeg',
    'image/png',
    'image/svg',
    'image/webp',
    'json',
    'robots.txt',
    'xml',
]


@pytest.mark.parametrize('method', HTTPBIN_METHODS)
@pytest.mark.parametrize('field', ['params', 'data', 'json'])
def test_all_methods(field, method, tempfile_session):
    """Test all relevant combinations of methods and data fields. Requests with different request
    params, data, or json should be cached under different keys.
    """
    url = httpbin(method.lower())
    for params in [{'param_1': 1}, {'param_1': 2}, {'param_2': 2}]:
        assert tempfile_session.request(method, url, **{field: params}).from_cache is False
        assert tempfile_session.request(method, url, **{field: params}).from_cache is True


@pytest.mark.parametrize('response_format', HTTPBIN_FORMATS)
def test_all_response_formats(response_format, tempfile_session):
    """Test that all relevant response formats are cached correctly"""
    # Temporary workaround for this issue: https://github.com/kevin1024/pytest-httpbin/issues/60
    if response_format == 'json' and USE_PYTEST_HTTPBIN:
        tempfile_session.allowable_codes = (200, 404)

    r1 = tempfile_session.get(httpbin(response_format))
    r2 = tempfile_session.get(httpbin(response_format))
    assert r1.from_cache is False
    assert r2.from_cache is True
    assert r1.content == r2.content


@pytest.mark.parametrize('n_redirects', range(1, 5))
@pytest.mark.parametrize('endpoint', ['redirect', 'absolute-redirect', 'relative-redirect'])
def test_redirects(endpoint, n_redirects, mock_session):
    """Test all types of redirect endpoints with different numbers of consecutive redirects"""
    mock_session.get(httpbin(f'redirect/{n_redirects}'))
    r2 = mock_session.get(httpbin('get'))

    assert r2.from_cache is True
    assert len(mock_session.cache.redirects) == n_redirects


def test_cookies(tempfile_session):
    def get_json(url):
        return json.loads(tempfile_session.get(url).text)

    response_1 = get_json(httpbin('cookies/set/test1/test2'))
    with tempfile_session.cache_disabled():
        assert get_json(httpbin('cookies')) == response_1
    # From cache
    response_2 = get_json(httpbin('cookies'))
    assert response_2 == get_json(httpbin('cookies'))
    # Not from cache
    with tempfile_session.cache_disabled():
        response_3 = get_json(httpbin('cookies/set/test3/test4'))
        assert response_3 == get_json(httpbin('cookies'))
