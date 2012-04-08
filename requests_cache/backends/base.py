#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    requests_cache.backends.base
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Contains base extensible in-memory cache backend and common functions
"""
from datetime import datetime
import requests


class MemoryCache(object):
    """ Represents in-memory cache.

    It can be easily extended to support other backends, such as file system.

    To extend it you can provide dictionary-like object for :attr:`url_map` and :attr:`responses`
    or override public methods.
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
        """
        self.responses[url] = reduce_response(response), datetime.now()
        self.url_map[url] = response.url
        for r in response.history:
            self.url_map[r.url] = response.url

    def get_response_and_time(self, url, default=(None, None)):
        """ Retrieves response and timestamp for `url` if it's stored in cache,
        otherwise returns `default`

        :param url: url of resource
        :param default: return this if `url` not found in cache
        :returns: tuple (response, datetime)
        """
        try:
            response, timestamp = self.responses[self.url_map[url]]
        except KeyError:
            return default
        return restore_response(response), timestamp

    def del_cached_url(self, url):
        """ Delete `url` from cache. Also deletes all urls from response history
        """
        try:
            response, _ = self.responses[url]
            for r in response.history:
                del self.url_map[r.url]
            del self.url_map[url]
            del self.responses[url]
        except KeyError:
            pass

    def clear(self):
        """ Clear cache
        """
        self.responses.clear()
        self.url_map.clear()

    def __str__(self):
        return 'urls: %s responses: %s' % (self.url_map, self.responses)


class _Store(object):
    pass

_fields_to_copy = ('_content', 'url', 'status_code', 'cookies',
                   'headers', 'encoding')

def reduce_response(response):
    result = _Store()
    # prefetch
    response.content
    for field in _fields_to_copy:
        setattr(result, field, getattr(response, field))
    result.history = []
    for r in response.history:
        result.history.append(reduce_response(r))
    return result

def restore_response(response):
    result = requests.Response()
    for field in _fields_to_copy:
        setattr(result, field, getattr(response, field))
    return result