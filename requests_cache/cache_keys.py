import hashlib
import json
from operator import itemgetter
from typing import Iterable, List, Mapping, Optional, Tuple, Union
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from requests import PreparedRequest, Request, Session
from requests.models import CaseInsensitiveDict
from requests.utils import default_headers
from url_normalize import url_normalize

DEFAULT_HEADERS = default_headers()
RequestContent = Union[Mapping, str, bytes]


def create_key(
    request: PreparedRequest,
    ignored_params: Iterable[str] = None,
    include_get_headers: bool = False,
    **kwargs,
) -> str:
    """Create a normalized cache key from a request object"""
    key = hashlib.sha256()
    key.update(encode((request.method or '').upper()))
    url = remove_ignored_url_params(request.url, ignored_params)
    url = url_normalize(url)
    key.update(encode(url))
    key.update(encode(kwargs.get('verify', True)))

    body = remove_ignored_body_params(request, ignored_params)
    if body:
        key.update(body)
    if include_get_headers and request.headers != DEFAULT_HEADERS:
        for name, value in normalize_dict(request.headers).items():  # type: ignore
            key.update(encode(f'{name}={value}'))

    return key.hexdigest()


def remove_ignored_params(
    request: PreparedRequest, ignored_params: Optional[Iterable[str]]
) -> PreparedRequest:
    if not ignored_params:
        return request
    request.headers = remove_ignored_headers(request.headers, ignored_params)
    request.url = remove_ignored_url_params(request.url, ignored_params)
    request.body = remove_ignored_body_params(request, ignored_params)
    return request


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
    request: PreparedRequest, ignored_parameters: Optional[Iterable[str]]
) -> bytes:
    original_body = request.body
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
        filtered_body = original_body  # type: ignore

    return encode(filtered_body)


def _filter_params(data: List[Tuple[str, str]], ignored_params: Iterable[str]) -> List[Tuple[str, str]]:
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
