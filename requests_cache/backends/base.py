#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    requests_cache.backends.base
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Contains BaseCache class which can be used as in-memory cache backend or
    extended to support persistence.
"""
from datetime import datetime
import requests


class BaseCache(object):
    """ Base class for cache implementations, can be used as in-memory cache.

    To extend it you can provide dictionary-like objects for
    :attr:`url_map` and :attr:`responses` or override public methods.
    """
    def __init__(self, location='memory', *args, **kwargs):
        #: `url` -> `key_in_cache` mapping
        self.url_map = {}
        #: `key_in_cache` -> `response` mapping
        self.responses = {}

    def save_response(self, url, response):
        """ Save response to cache

        :param url: url for this response

                    .. note:: urls from history saved automatically
        :param response: response to save

        .. note:: Response is reduced before saving (with :meth:`reduce_response`)
                  to make it picklable
        """
        self.responses[url] = self.reduce_response(response), datetime.now()


    def add_url_mapping(self, url1, url2):
        self.url_map[url1] = url2


    def get_response_and_time(self, url, default=(None, None)):
        """ Retrieves response and timestamp for `url` if it's stored in cache,
        otherwise returns `default`

        :param url: url of resource
        :param default: return this if `url` not found in cache
        :returns: tuple (response, datetime)

        .. note:: Response is restored after unpickling with :meth:`restore_response`
        """
        try:
            if url not in self.responses:
                url = self.url_map[url]
            response, timestamp = self.responses[url]
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
                response, _ = self.responses[self.url_map[key]]
                del self.url_map[key]
            for r in response.history:
                del self.url_map[r.url]
        except KeyError:
            pass

    def clear(self):
        """ Clear cache
        """
        self.responses.clear()
        self.url_map.clear()

    def has_key(self, key):
        """ Returns `True` if cache has `key`, `False` otherwise
        """
        return key in self.responses or key in self.url_map

    _response_attrs = ['_content', 'url', 'status_code', 'cookies',
                       'headers', 'encoding']

    def reduce_response(self, response):
        """ Reduce response object to make it compatible with ``pickle``
        """
        result = _Store()
        # prefetch
        response.content
        for field in self._response_attrs:
            setattr(result, field, getattr(response, field))
        result.history = [self.reduce_response(r) for r in response.history]
        return result

    def restore_response(self, response):
        """ Restore response object after unpickling
        """
        result = requests.Response()
        for field in self._response_attrs:
            setattr(result, field, getattr(response, field))
        result.history = [self.restore_response(r) for r in response.history]
        return result

    def __str__(self):
        return 'urls: %s\nresponses: %s' % (self.url_map, self.responses)


# used for saving response attributes
class _Store(object):
    pass