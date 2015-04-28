#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    requests_cache.backends.base
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Contains BaseCache class which can be used as in-memory cache backend or
    extended to support persistence.
"""
from datetime import datetime
import hashlib
from copy import copy
from io import BytesIO

import requests

from ..compat import is_py2


_DEFAULT_HEADERS = requests.utils.default_headers()


class BaseCache(object):
    """ Base class for cache implementations, can be used as in-memory cache.

    To extend it you can provide dictionary-like objects for
    :attr:`keys_map` and :attr:`responses` or override public methods.
    """
    def __init__(self, *args, **kwargs):
        #: `key` -> `key_in_responses` mapping
        self.keys_map = {}
        #: `key_in_cache` -> `response` mapping
        self.responses = {}
        self._include_get_headers = kwargs.get("include_get_headers", False)

    def save_response(self, key, response):
        """ Save response to cache

        :param key: key for this response
        :param response: response to save

        .. note:: Response is reduced before saving (with :meth:`reduce_response`)
                  to make it picklable
        """
        self.responses[key] = self.reduce_response(response), datetime.utcnow()

    def add_key_mapping(self, new_key, key_to_response):
        """
        Adds mapping of `new_key` to `key_to_response` to make it possible to
        associate many keys with single response

        :param new_key: new key (e.g. url from redirect)
        :param key_to_response: key which can be found in :attr:`responses`
        :return:
        """
        self.keys_map[new_key] = key_to_response

    def get_response_and_time(self, key, default=(None, None)):
        """ Retrieves response and timestamp for `key` if it's stored in cache,
        otherwise returns `default`

        :param key: key of resource
        :param default: return this if `key` not found in cache
        :returns: tuple (response, datetime)

        .. note:: Response is restored after unpickling with :meth:`restore_response`
        """
        try:
            if key not in self.responses:
                key = self.keys_map[key]
            response, timestamp = self.responses[key]
        except KeyError:
            return default
        return self.restore_response(response), timestamp

    def delete(self, key):
        """ Delete `key` from cache. Also deletes all responses from response history
        """
        try:
            if key in self.responses:
                response, _ = self.responses[key]
                del self.responses[key]
            else:
                response, _ = self.responses[self.keys_map[key]]
                del self.keys_map[key]
            for r in response.history:
                del self.keys_map[self.create_key(r.request)]
        except KeyError:
            pass

    def delete_url(self, url):
        """ Delete response associated with `url` from cache.
        Also deletes all responses from response history. Works only for GET requests
        """
        self.delete(self._url_to_key(url))

    def clear(self):
        """ Clear cache
        """
        self.responses.clear()
        self.keys_map.clear()

    def has_key(self, key):
        """ Returns `True` if cache has `key`, `False` otherwise
        """
        return key in self.responses or key in self.keys_map

    def has_url(self, url):
        """ Returns `True` if cache has `url`, `False` otherwise.
        Works only for GET request urls
        """
        return self.has_key(self._url_to_key(url))

    def _url_to_key(self, url):
        session = requests.Session()
        return self.create_key(session.prepare_request(requests.Request('GET', url)))

    _response_attrs = ['_content', 'url', 'status_code', 'cookies',
                       'headers', 'encoding', 'request', 'reason', 'raw']

    _raw_response_attrs = ['_original_response', 'decode_content', 'headers',
                            'reason', 'status', 'strict', 'version']

    def reduce_response(self, response, seen=None):
        """ Reduce response object to make it compatible with ``pickle``
        """
        if seen is None:
            seen = {}
        try:
            return seen[id(response)]
        except KeyError:
            pass
        result = _Store()
        # prefetch
        response.content
        for field in self._response_attrs:
            setattr(result, field, self._picklable_field(response, field))
        seen[id(response)] = result
        result.history = tuple(self.reduce_response(r, seen) for r in response.history)
        return result

    def _picklable_field(self, response, name):
        value = getattr(response, name)
        if name == 'request':
            value = copy(value)
            value.hooks = []
        elif name == 'raw':
            result = _RawStore()
            for field in self._raw_response_attrs:
                setattr(result, field, getattr(value, field, None))
            if result._original_response is not None:
                setattr(result._original_response, "fp", None)  # _io.BufferedReader is not picklable
            value = result
        return value

    def restore_response(self, response, seen=None):
        """ Restore response object after unpickling
        """
        if seen is None:
            seen = {}
        try:
            return seen[id(response)]
        except KeyError:
            pass
        result = requests.Response()
        for field in self._response_attrs:
            setattr(result, field, getattr(response, field, None))
        result.raw._cached_content_ = result.content
        seen[id(response)] = result
        result.history = tuple(self.restore_response(r, seen) for r in response.history)
        return result

    def create_key(self, request):
        key = hashlib.sha256()
        key.update(_to_bytes(request.method.upper()))
        key.update(_to_bytes(request.url))
        if request.body:
            key.update(_to_bytes(request.body))
        else:
            if self._include_get_headers and request.headers != _DEFAULT_HEADERS:
                for name, value in sorted(request.headers.items()):
                    key.update(_to_bytes(name))
                    key.update(_to_bytes(value))
        return key.hexdigest()

    def __str__(self):
        return 'keys: %s\nresponses: %s' % (self.keys_map, self.responses)


# used for saving response attributes
class _Store(object):
    pass


class _RawStore(object):
    # noop for cached response
    def release_conn(self):
        pass

    # for streaming requests support
    def read(self, chunk_size=1):
        if not hasattr(self, "_io_with_content_"):
            self._io_with_content_ = BytesIO(self._cached_content_)
        return self._io_with_content_.read(chunk_size)


def _to_bytes(s, encoding='utf-8'):
    if is_py2 or isinstance(s, bytes):
        return s
    return bytes(s, encoding)
