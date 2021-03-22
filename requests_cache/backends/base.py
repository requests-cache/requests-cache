"""
    requests_cache.backends.base
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Contains BaseCache class which can be used as in-memory cache backend or
    extended to support persistence.
"""
import hashlib
import json
from pickle import PickleError
from typing import List
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

from ..response import AnyResponse, CachedResponse, ExpirationTime

DEFAULT_HEADERS = requests.utils.default_headers()


class BaseCache(object):
    """Base class for cache implementations, which can also be used as in-memory cache.

    To extend it you can provide dictionary-like objects for
    :attr:`keys_map` and :attr:`responses` or override public methods.
    """

    def __init__(self, *args, **kwargs):
        #: `key` -> `key_in_responses` mapping
        self.keys_map = {}
        #: `key_in_cache` -> `response` mapping
        self.responses = {}
        self._include_get_headers = kwargs.get("include_get_headers", False)
        self._ignored_parameters = set(kwargs.get("ignored_parameters") or [])

    @property
    def urls(self) -> List[str]:
        """Get all URLs currently in the cache"""
        response_urls = [response.url for response in self.responses.values()]
        redirect_urls = list(self.keys_map.keys())
        return sorted(response_urls + redirect_urls)

    def save_response(self, key: str, response: AnyResponse, expire_after: ExpirationTime = None):
        """Save response to cache

        Args:
            key: key for this response
            response: response to save
            expire_after: Time in seconds until this cache item should expire
        """
        self.responses[key] = CachedResponse(response, expire_after=expire_after)

    def add_key_mapping(self, new_key: str, key_to_response: str):
        """
        Adds mapping of `new_key` to `key_to_response` to make it possible to
        associate many keys with single response

        Args:
            new_key: New resource key (e.g. url from redirect)
            key_to_response: Key which can be found in :attr:`responses`
        """
        self.keys_map[new_key] = key_to_response

    def get_response(self, key: str, default=None) -> CachedResponse:
        """Retrieves response for `key` if it's stored in cache, otherwise returns `default`

        Args:
            key: Key of resource
            default: Value to return if `key` is not in cache
        """
        try:
            if key not in self.responses:
                key = self.keys_map[key]
            response = self.responses[key]
            response.reset()  # In case response was in memory and raw content has already been read
            return response
        except (KeyError, TypeError, PickleError):
            return default

    def delete(self, key: str):
        """Delete `key` from cache. Also deletes all responses from response history"""
        try:
            if key in self.responses:
                response = self.responses[key]
                del self.responses[key]
            else:
                response = self.responses[self.keys_map[key]]
                del self.keys_map[key]
            for r in response.history:
                del self.keys_map[self.create_key(r.request)]
        except KeyError:
            pass

    def delete_url(self, url: str):
        """Delete response associated with `url` from cache.
        Also deletes all responses from response history. Works only for GET requests
        """
        self.delete(self._url_to_key(url))

    def clear(self):
        """Delete all items from the cache"""
        self.responses.clear()
        self.keys_map.clear()

    def remove_expired_responses(self, expire_after: ExpirationTime = None):
        """Remove expired responses from the cache, optionally with revalidation

        Args:
            expire_after: A new expiration time used to revalidate the cache
        """
        for key, response in list(self.responses.items()):
            # If we're revalidating and it's not yet expired, update the cached item's expiration
            if expire_after is not None and not response.revalidate(expire_after):
                self.responses[key] = response
            if response.is_expired:
                self.delete(key)

    def has_key(self, key: str) -> bool:
        """Returns `True` if cache has `key`, `False` otherwise"""
        return key in self.responses or key in self.keys_map

    def has_url(self, url: str) -> bool:
        """Returns `True` if cache has `url`, `False` otherwise. Works only for GET request urls"""
        return self.has_key(self._url_to_key(url))  # noqa: W601

    def _url_to_key(self, url: str) -> str:
        session = requests.Session()
        return self.create_key(session.prepare_request(requests.Request('GET', url)))

    def create_key(self, request: requests.PreparedRequest) -> str:
        url = self._remove_ignored_url_parameters(request)
        body = self._remove_ignored_body_parameters(request)
        key = hashlib.sha256()
        key.update(_encode(request.method.upper()))
        key.update(_encode(url))

        if body:
            key.update(_encode(body))
        else:
            if self._include_get_headers and request.headers != DEFAULT_HEADERS:
                for name, value in sorted(request.headers.items()):
                    key.update(_encode(name))
                    key.update(_encode(value))
        return key.hexdigest()

    def _remove_ignored_url_parameters(self, request: requests.PreparedRequest) -> str:
        url = str(request.url)
        if not self._ignored_parameters:
            return url

        url = urlparse(url)
        query = parse_qsl(url.query)
        query = self._filter_ignored_parameters(query)
        query = urlencode(query)
        url = urlunparse((url.scheme, url.netloc, url.path, url.params, query, url.fragment))
        return url

    def _remove_ignored_body_parameters(self, request: requests.PreparedRequest) -> str:
        body = request.body
        content_type = request.headers.get('content-type')
        if not self._ignored_parameters or not body or not content_type:
            return request.body

        if content_type == 'application/x-www-form-urlencoded':
            body = parse_qsl(body)
            body = self._filter_ignored_parameters(body)
            body = urlencode(body)
        elif content_type == 'application/json':
            body = json.loads(_decode(body))
            body = self._filter_ignored_parameters(sorted(body.items()))
            body = json.dumps(body)
        return body

    def _filter_ignored_parameters(self, data):
        return [(k, v) for k, v in data if k not in self._ignored_parameters]

    def __str__(self):
        return f'redirects: {len(self.keys_map)}\nresponses: {len(self.responses)}'


def _encode(value, encoding='utf-8') -> bytes:
    """Encode a value, if it hasn't already been"""
    return value if isinstance(value, bytes) else value.encode(encoding)


def _decode(value, encoding='utf-8') -> str:
    """Decode a value, if hasn't already been.
    Note: PreparedRequest.body is always encoded in utf-8.
    """
    return value if isinstance(value, str) else value.decode(encoding)
