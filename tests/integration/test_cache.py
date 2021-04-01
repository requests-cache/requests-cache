"""CachedSession tests that hit a containerized httpbin service"""
import json

from tests.conftest import httpbin


def test_cookies(mock_session):
    def get_json(url):
        return json.loads(mock_session.get(url).text)

    response_1 = get_json(httpbin('cookies/set/test1/test2'))
    with mock_session.cache_disabled():
        assert get_json(httpbin('cookies')) == response_1
    # From cache
    response_2 = get_json(httpbin('cookies'))
    assert response_2 == get_json(httpbin('cookies'))
    # Not from cache
    with mock_session.cache_disabled():
        response_3 = get_json(httpbin('cookies/set/test3/test4'))
        assert response_3 == get_json(httpbin('cookies'))


def test_gzip(mock_session):
    assert mock_session.get(httpbin('gzip')).from_cache is False
    assert mock_session.get(httpbin('gzip')).from_cache is True
