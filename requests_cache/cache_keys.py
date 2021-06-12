import hashlib
import json
from operator import itemgetter
from typing import Iterable, List, Mapping, Tuple, Union
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from url_normalize import url_normalize

DEFAULT_HEADERS = requests.utils.default_headers()
RequestContent = Union[Mapping, str, bytes]


def create_key(
    request: requests.PreparedRequest,
    ignored_params: Iterable[str] = None,
    include_get_headers: bool = False,
    **kwargs,
) -> str:
    """Create a normalized cache key from a request object"""
    key = hashlib.sha256()
    key.update(encode(request.method.upper()))
    url = remove_ignored_url_params(request, ignored_params)
    url = url_normalize(url)
    key.update(encode(url))
    key.update(encode(kwargs.get('verify', True)))

    body = remove_ignored_body_params(request, ignored_params)
    if body:
        key.update(body)
    if include_get_headers and request.headers != DEFAULT_HEADERS:
        for name, value in normalize_dict(request.headers).items():
            key.update(encode(f'{name}={value}'))

    return key.hexdigest()


def remove_ignored_params(
    request: requests.PreparedRequest, ignored_params: Iterable[str]
) -> requests.PreparedRequest:
    if not ignored_params:
        return request
    request.headers = remove_ignored_headers(request, ignored_params)
    request.url = remove_ignored_url_params(request, ignored_params)
    request.body = remove_ignored_body_params(request, ignored_params)
    return request


def remove_ignored_headers(request: requests.PreparedRequest, ignored_params: Iterable[str]) -> dict:
    if not ignored_params:
        return request.headers
    headers = request.headers.copy()
    headers.update({k: None for k in ignored_params})
    return headers


def remove_ignored_url_params(request: requests.PreparedRequest, ignored_params: Iterable[str]) -> str:
    url = str(request.url)
    if not ignored_params:
        return url

    url = urlparse(url)
    query = parse_qsl(url.query)
    query = filter_params(query, ignored_params)
    query = urlencode(query)
    url = urlunparse((url.scheme, url.netloc, url.path, url.params, query, url.fragment))
    return url


def remove_ignored_body_params(
    request: requests.PreparedRequest, ignored_params: Iterable[str]
) -> bytes:
    body = request.body
    content_type = request.headers.get('content-type')
    if not ignored_params or not body or not content_type:
        return encode(request.body)

    if content_type == 'application/x-www-form-urlencoded':
        body = parse_qsl(body)
        body = filter_params(body, ignored_params)
        body = urlencode(body)
    elif content_type == 'application/json':
        body = json.loads(decode(body))
        body = filter_params(sorted(body.items()), ignored_params)
        body = json.dumps(body)
    return encode(body)


def filter_params(data: List[Tuple], ignored_params: Iterable[str]) -> List[Tuple]:
    return [(k, v) for k, v in data if k not in set(ignored_params)]


def normalize_dict(items: RequestContent = None, normalize_data: bool = True) -> RequestContent:
    """Sort items in a dict

    Args:
        items: Request params, data, or json
        normalize_data: Also normalize stringified JSON
    """

    def sort_dict(d):
        return dict(sorted(d.items(), key=itemgetter(0)))

    if isinstance(items, Mapping):
        return sort_dict(items)
    if normalize_data and isinstance(items, (bytes, str)):
        # Attempt to load body as JSON; not doing this by default as it could impact performance
        try:
            dict_items = json.loads(decode(items))
            dict_items = json.dumps(sort_dict(dict_items))
            return dict_items.encode('utf-8') if isinstance(items, bytes) else dict_items
        except Exception:
            pass

    return items


def url_to_key(url: str, *args, **kwargs) -> str:
    request = requests.Session().prepare_request(requests.Request('GET', url))
    return create_key(request, *args, **kwargs)


def encode(value, encoding='utf-8') -> bytes:
    """Encode a value to bytes, if it hasn't already been"""
    return value if isinstance(value, bytes) else str(value).encode(encoding)


def decode(value, encoding='utf-8') -> str:
    """Decode a value from bytes, if hasn't already been.
    Note: PreparedRequest.body is always encoded in utf-8.
    """
    return value.decode(encoding) if isinstance(value, bytes) else value
