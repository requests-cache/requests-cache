"""Internal utilities for generating cache keys that are used for request matching

.. automodsumm:: requests_cache.cache_keys
   :functions-only:
   :nosignatures:
"""
from __future__ import annotations

import json
from hashlib import blake2b
from logging import getLogger
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Mapping, Optional, Union
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from requests import Request, Session
from requests.models import CaseInsensitiveDict
from url_normalize import url_normalize

from ._utils import decode, encode, get_valid_kwargs

__all__ = ['create_key', 'normalize_request']
if TYPE_CHECKING:
    from .models import AnyPreparedRequest, AnyRequest, CachedResponse

# Maximum JSON request body size that will be normalized
MAX_NORM_BODY_SIZE = 10 * 1024 * 1024

ParamList = Optional[Iterable[str]]
RequestContent = Union[Mapping, str, bytes]

logger = getLogger(__name__)


def create_key(
    request: AnyRequest = None,
    ignored_parameters: ParamList = None,
    match_headers: Union[ParamList, bool] = False,
    serializer: Any = None,
    **request_kwargs,
) -> str:
    """Create a normalized cache key from either a request object or :py:class:`~requests.Request`
    arguments

    Args:
        request: Request object to generate a cache key from
        ignored_parameters: Request paramters, headers, and/or JSON body params to exclude
        match_headers: Match only the specified headers, or ``True`` to match all headers
        request_kwargs: Request arguments to generate a cache key from
    """
    # Convert raw request arguments into a request object, if needed
    if not request:
        request = Request(**get_valid_kwargs(Request.__init__, request_kwargs))

    # Normalize and gather all relevant request info to match against
    request = normalize_request(request, ignored_parameters)
    key_parts = [
        request.method or '',
        request.url,
        request.body or '',
        request_kwargs.get('verify', True),
        *get_matched_headers(request.headers, match_headers),
        str(serializer),
    ]

    # Generate a hash based on this info
    key = blake2b(digest_size=8)
    for part in key_parts:
        key.update(encode(part))
    return key.hexdigest()


def get_matched_headers(
    headers: CaseInsensitiveDict, match_headers: Union[ParamList, bool]
) -> List[str]:
    """Get only the headers we should match against as a list of ``k=v`` strings, given an optional
    include list.
    """
    if not match_headers:
        return []
    if match_headers is True:
        match_headers = headers
    return [
        f'{k.lower()}={headers[k]}'
        for k in sorted(match_headers, key=lambda x: x.lower())
        if k in headers
    ]


def normalize_request(
    request: AnyRequest, ignored_parameters: ParamList = None
) -> AnyPreparedRequest:
    """Normalize and remove ignored parameters from request URL, body, and headers.
    This is used for both:

    * Increasing cache hits by generating more precise cache keys
    * Redacting potentially sensitive info from cached requests

    Args:
        request: Request object to normalize
        ignored_parameters: Request paramters, headers, and/or JSON body params to exclude
    """
    if isinstance(request, Request):
        norm_request: AnyPreparedRequest = Session().prepare_request(request)
    else:
        norm_request = request.copy()

    norm_request.method = (norm_request.method or '').upper()
    norm_request.url = normalize_url(norm_request.url or '', ignored_parameters)
    norm_request.headers = normalize_headers(norm_request.headers, ignored_parameters)
    norm_request.body = normalize_body(norm_request, ignored_parameters)
    return norm_request


def normalize_headers(
    headers: Mapping[str, str], ignored_parameters: ParamList
) -> CaseInsensitiveDict:
    """Sort and filter request headers"""
    if ignored_parameters:
        headers = filter_sort_dict(headers, ignored_parameters)
    return CaseInsensitiveDict(headers)


def normalize_url(url: str, ignored_parameters: ParamList) -> str:
    """Normalize and filter a URL. This includes request parameters, IDN domains, scheme, host,
    port, etc.
    """
    # Strip query params from URL, sort and filter, and reassemble into a complete URL
    url_tokens = urlparse(url)
    url = urlunparse(
        (
            url_tokens.scheme,
            url_tokens.netloc,
            url_tokens.path,
            url_tokens.params,
            normalize_params(url_tokens.query, ignored_parameters),
            url_tokens.fragment,
        )
    )

    return url_normalize(url)


def normalize_body(request: AnyPreparedRequest, ignored_parameters: ParamList) -> bytes:
    """Normalize and filter a request body if possible, depending on Content-Type"""
    original_body = request.body or b''
    content_type = request.headers.get('Content-Type')

    # Filter and sort params if possible
    filtered_body: Union[str, bytes] = original_body
    if content_type == 'application/json':
        filtered_body = normalize_json_body(original_body, ignored_parameters)
    elif content_type == 'application/x-www-form-urlencoded':
        filtered_body = normalize_params(original_body, ignored_parameters)

    return encode(filtered_body)


def normalize_json_body(
    original_body: Union[str, bytes], ignored_parameters: ParamList
) -> Union[str, bytes]:
    """Normalize and filter a request body with serialized JSON data"""
    if len(original_body) <= 2 or len(original_body) > MAX_NORM_BODY_SIZE:
        return original_body

    try:
        body = json.loads(decode(original_body))
        body = filter_sort_json(body, ignored_parameters)
        return json.dumps(body)
    # If it's invalid JSON, then don't mess with it
    except (AttributeError, TypeError, ValueError):
        logger.debug('Invalid JSON body')
        return original_body


def normalize_params(value: Union[str, bytes], ignored_parameters: ParamList) -> str:
    """Normalize and filter urlencoded params from either a URL or request body with form data"""
    query_str = decode(value)
    params = dict(parse_qsl(query_str))

    # parse_qsl doesn't handle key-only params, so add those here
    key_only_params = [k for k in query_str.split('&') if k and '=' not in k]
    params.update({k: '' for k in key_only_params})

    params = filter_sort_dict(params, ignored_parameters)
    return urlencode(params)


def redact_response(response: CachedResponse, ignored_parameters: ParamList) -> CachedResponse:
    """Redact any ignored parameters (potentially containing sensitive info) from a cached request"""
    if ignored_parameters:
        response.url = normalize_url(response.url, ignored_parameters)
        response.request = normalize_request(response.request, ignored_parameters)  # type: ignore
    return response


def filter_sort_json(data: Union[List, Mapping], ignored_parameters: ParamList):
    if isinstance(data, Mapping):
        return filter_sort_dict(data, ignored_parameters)
    else:
        return filter_sort_list(data, ignored_parameters)


def filter_sort_dict(data: Mapping[str, str], ignored_parameters: ParamList) -> Dict[str, str]:
    if not ignored_parameters:
        return dict(sorted(data.items()))
    return {k: v for k, v in sorted(data.items()) if k not in set(ignored_parameters)}


def filter_sort_list(data: List, ignored_parameters: ParamList) -> List:
    if not ignored_parameters:
        return sorted(data)
    return [k for k in sorted(data) if k not in set(ignored_parameters)]
