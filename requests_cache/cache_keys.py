"""Internal utilities for generating the cache keys that are used to match requests

.. automodsumm:: requests_cache.cache_keys
   :functions-only:
   :nosignatures:
"""
from __future__ import annotations

import json
from hashlib import blake2b
from operator import itemgetter
from typing import TYPE_CHECKING, Dict, Iterable, List, Mapping, Optional, Tuple, Union
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from requests import Request, Session
from requests.models import CaseInsensitiveDict
from requests.utils import default_headers
from url_normalize import url_normalize

from . import get_valid_kwargs

if TYPE_CHECKING:
    from .models import AnyRequest

DEFAULT_REQUEST_HEADERS = default_headers()
DEFAULT_EXCLUDE_HEADERS = {'Cache-Control', 'If-None-Match', 'If-Modified-Since'}
RequestContent = Union[Mapping, str, bytes]


def create_key(
    request: AnyRequest = None,
    ignored_parameters: Iterable[str] = None,
    match_headers: Union[Iterable[str], bool] = False,
    **kwargs,
) -> str:
    """Create a normalized cache key from either a request object or :py:class:`~requests.Request`
    arguments
    """
    # Create a PreparedRequest, if needed
    if not request:
        request_kwargs = get_valid_kwargs(Request.__init__, kwargs)
        request = Session().prepare_request(Request(**request_kwargs))
    if TYPE_CHECKING:
        assert request is not None

    # Add method and relevant request settings
    key = blake2b(digest_size=8)
    key.update(encode((request.method or '').upper()))
    key.update(encode(kwargs.get('verify', True)))

    # Add filtered/normalized URL + request params
    url = remove_ignored_url_params(request.url, ignored_parameters)
    key.update(encode(url_normalize(url)))

    # Add filtered request body
    body = remove_ignored_body_params(request, ignored_parameters)
    if body:
        key.update(body)

    # Add filtered/normalized headers
    headers = get_matched_headers(request.headers, ignored_parameters, match_headers)
    for k, v in headers.items():
        key.update(encode(f'{k}={v}'))

    return key.hexdigest()


def get_matched_headers(
    headers: CaseInsensitiveDict, ignored_parameters: Optional[Iterable[str]], match_headers
) -> Dict:
    """Get only the headers we should match against, given an optional include list and/or exclude
    list. Also normalizes headers (sorted/lowercased keys).
    """
    if not match_headers:
        return {}

    included = set(match_headers if isinstance(match_headers, Iterable) else headers.keys())
    included -= set(ignored_parameters or [])
    included -= DEFAULT_EXCLUDE_HEADERS
    return {k.lower(): headers[k] for k in sorted(included) if k in headers}


def remove_ignored_headers(
    headers: Mapping, ignored_parameters: Optional[Iterable[str]]
) -> CaseInsensitiveDict:
    """Remove any ignored request headers"""
    if not ignored_parameters:
        return CaseInsensitiveDict(headers)

    headers = CaseInsensitiveDict(headers)
    for k in ignored_parameters:
        headers.pop(k, None)
    return headers


def remove_ignored_params(
    request: AnyRequest, ignored_parameters: Optional[Iterable[str]]
) -> AnyRequest:
    """Remove ignored parameters from request URL, body, and headers"""
    if not ignored_parameters:
        return request
    request.headers = remove_ignored_headers(request.headers, ignored_parameters)
    request.url = remove_ignored_url_params(request.url, ignored_parameters)
    request.body = remove_ignored_body_params(request, ignored_parameters)
    return request


def remove_ignored_url_params(url: Optional[str], ignored_parameters: Optional[Iterable[str]]) -> str:
    """Remove any ignored request parameters from the URL"""
    if not ignored_parameters or not url:
        return url or ''

    url_tokens = urlparse(url)
    query = _filter_params(parse_qsl(url_tokens.query), ignored_parameters)
    return urlunparse(
        (
            url_tokens.scheme,
            url_tokens.netloc,
            url_tokens.path,
            url_tokens.params,
            urlencode(query),
            url_tokens.fragment,
        )
    )


def remove_ignored_body_params(
    request: AnyRequest, ignored_parameters: Optional[Iterable[str]]
) -> bytes:
    """Remove any ignored parameters from the request body"""
    original_body = request.body
    filtered_body: Union[str, bytes] = b''
    content_type = request.headers.get('content-type')
    if not ignored_parameters or not original_body or not content_type:
        return encode(original_body)

    if content_type == 'application/x-www-form-urlencoded':
        body = _filter_params(parse_qsl(decode(original_body)), ignored_parameters)
        filtered_body = urlencode(body)
    elif content_type == 'application/json':
        body = json.loads(decode(original_body)).items()
        body = _filter_params(sorted(body), ignored_parameters)
        filtered_body = json.dumps(body)
    else:
        filtered_body = original_body

    return encode(filtered_body)


def _filter_params(
    data: List[Tuple[str, str]], ignored_parameters: Iterable[str]
) -> List[Tuple[str, str]]:
    return [(k, v) for k, v in data if k not in set(ignored_parameters)]


def normalize_dict(
    items: Optional[RequestContent], normalize_data: bool = True
) -> Optional[RequestContent]:
    """Sort items in a dict

    Args:
        items: Request params, data, or json
        normalize_data: Also normalize stringified JSON
    """
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


def sort_dict(d: Mapping) -> Dict:
    return dict(sorted(d.items(), key=itemgetter(0)))


def encode(value, encoding='utf-8') -> bytes:
    """Encode a value to bytes, if it hasn't already been"""
    return value if isinstance(value, bytes) else str(value).encode(encoding)


def decode(value, encoding='utf-8') -> str:
    """Decode a value from bytes, if hasn't already been.
    Note: ``PreparedRequest.body`` is always encoded in utf-8.
    """
    return value.decode(encoding) if isinstance(value, bytes) else value
