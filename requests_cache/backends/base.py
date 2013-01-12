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
import requests


class BaseCache(object):
    """ Base class for cache implementations, can be used as in-memory cache.

    To extend it you can provide dictionary-like objects for
    :attr:`keys_map` and :attr:`responses` or override public methods.
    """
    def __init__(self, location='memory', *args, **kwargs):
        #: `key` -> `key_in_responses` mapping
        self.keys_map = {}
        #: `key_in_cache` -> `response` mapping
        self.responses = {}

    def save_response(self, key, response):
        """ Save response to cache

        :param key: key for this response
        :param response: response to save

        .. note:: Response is reduced before saving (with :meth:`reduce_response`)
                  to make it picklable
        """
        self.responses[key] = self.reduce_response(response), datetime.now()

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
        """ Delete `key` from cache. Also deletes all urls from response history
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

    def clear(self):
        """ Clear cache
        """
        self.responses.clear()
        self.keys_map.clear()

    def has_key(self, key):
        """ Returns `True` if cache has `key`, `False` otherwise
        """
        return key in self.responses or key in self.keys_map

    _response_attrs = ['_content', 'url', 'status_code', 'cookies',
                       'headers', 'encoding', 'request', 'reason']

    def reduce_response(self, response):
        """ Reduce response object to make it compatible with ``pickle``
        """
        result = _Store()
        # prefetch
        response.content
        for field in self._response_attrs:
            setattr(result, field, getattr(response, field))
        result.history = tuple(self.reduce_response(r) for r in response.history)
        return result

    def restore_response(self, response):
        """ Restore response object after unpickling
        """
        result = requests.Response()
        for field in self._response_attrs:
            setattr(result, field, getattr(response, field))
        result.history = tuple(self.restore_response(r) for r in response.history)
        return result

    def create_key(self, request):
        cache_data = request.method.upper() + request.url
        if request.body:
            cache_data += str(request.body)
        return hashlib.sha256(cache_data).hexdigest()

    def __str__(self):
        return 'keys: %s\nresponses: %s' % (self.keys_map, self.responses)


# used for saving response attributes
class _Store(object):
    pass