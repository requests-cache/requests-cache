"""The cache_keys module is mostly covered indirectly via other tests.
This just contains a couple extra edge cases not covered elsewhere.
"""
from requests import PreparedRequest

from requests_cache.cache_keys import normalize_dict, remove_ignored_body_params, remove_ignored_headers


def test_normalize_dict__skip_body():
    assert normalize_dict(b'some bytes', normalize_data=False) == b'some bytes'


def test_remove_ignored_body_params__binary():
    request = PreparedRequest()
    request.url = 'https://img.site.com/base/img.jpg'
    request.body = b'some bytes'
    request.headers = {'Content-Type': 'application/octet-stream'}
    assert remove_ignored_body_params(request, ignored_parameters=None) == request.body


def test_remove_ignored_headers__empty():
    request = PreparedRequest()
    request.url = 'https://img.site.com/base/img.jpg'
    request.headers = {'foo': 'bar'}
    assert remove_ignored_headers(request, ignored_parameters=None) == request.headers
