from __future__ import annotations

import hashlib
import json
from operator import itemgetter
from typing import TYPE_CHECKING, Iterable, List, Mapping, Optional, Tuple, Union
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from requests import Request, Session
from requests.models import CaseInsensitiveDict
from requests.utils import default_headers
from url_normalize import url_normalize

if TYPE_CHECKING:
    from .models import AnyRequest

DEFAULT_HEADERS = default_headers()
RequestContent = Union[Mapping, str, bytes]


def create_key(
    request: AnyRequest,
    ignored_params: Iterable[str] = None,
    include_get_headers: bool = False,
    **kwargs,
) -> str:
    """Create a normalized cache key from a request object"""
    key = hashlib.sha256()
    key.update(encode((request.method or '').upper()))
    url = remove_ignored_url_params(request, ignored_params)
    url = url_normalize(url)
    key.update(encode(url))
    key.update(encode(kwargs.get('verify', True)))

    body = remove_ignored_body_params(request, ignored_params)
    if body:
        key.update(body)
    if include_get_headers and request.headers != DEFAULT_HEADERS:
        headers = normalize_dict(request.headers)
        if TYPE_CHECKING:
            assert isinstance(headers, dict)
        for name, value in headers.items():
            key.update(encode(f'{name}={value}'))

    return key.hexdigest()


def remove_ignored_params(request: AnyRequest, ignored_params: Optional[Iterable[str]]) -> AnyRequest:
    if not ignored_params:
        return request
    request.headers = remove_ignored_headers(request, ignored_params)
    request.url = remove_ignored_url_params(request, ignored_params)
    request.body = remove_ignored_body_params(request, ignored_params)
    return request


def remove_ignored_headers(
    request: AnyRequest, ignored_params: Optional[Iterable[str]]
) -> CaseInsensitiveDict:
    if not ignored_params:
        return request.headers
    headers = CaseInsensitiveDict(request.headers.copy())
    for k in ignored_params:
        headers.pop(k, None)
    return headers


def remove_ignored_url_params(request: AnyRequest, ignored_params: Optional[Iterable[str]]) -> str:
    url_str = str(request.url)
    if not ignored_params:
        return url_str

    url = urlparse(url_str)
    query = filter_params(parse_qsl(url.query), ignored_params)
    return urlunparse((url.scheme, url.netloc, url.path, url.params, urlencode(query), url.fragment))


def remove_ignored_body_params(request: AnyRequest, ignored_params: Optional[Iterable[str]]) -> bytes:
    original_body = request.body
    filtered_body: Union[str, bytes] = b''
    content_type = request.headers.get('content-type')
    if not ignored_params or not original_body or not content_type:
        return encode(original_body)

    if content_type == 'application/x-www-form-urlencoded':
        body = filter_params(parse_qsl(decode(original_body)), ignored_params)
        filtered_body = urlencode(body)
    elif content_type == 'application/json':
        body = json.loads(decode(original_body)).items()
        body = filter_params(sorted(body), ignored_params)
        filtered_body = json.dumps(body)
    else:
        filtered_body = original_body

    return encode(filtered_body)


def filter_params(data: List[Tuple[str, str]], ignored_params: Iterable[str]) -> List[Tuple[str, str]]:
    return [(k, v) for k, v in data if k not in set(ignored_params)]


def normalize_dict(
    items: Optional[RequestContent], normalize_data: bool = True
) -> Optional[RequestContent]:
    """Sort items in a dict

    Args:
        items: Request params, data, or json
        normalize_data: Also normalize stringified JSON
    """

    def sort_dict(d):
        return dict(sorted(d.items(), key=itemgetter(0)))

    if not items:
        return None
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
    request = Session().prepare_request(Request('GET', url))
    return create_key(request, *args, **kwargs)


def encode(value, encoding='utf-8') -> bytes:
    """Encode a value to bytes, if it hasn't already been"""
    return value if isinstance(value, bytes) else str(value).encode(encoding)


def decode(value, encoding='utf-8') -> str:
    """Decode a value from bytes, if hasn't already been.
    Note: PreparedRequest.body is always encoded in utf-8.
    """
    return value.decode(encoding) if isinstance(value, bytes) else value
