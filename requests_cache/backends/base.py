#!/usr/bin/env python
# -*- coding: utf-8 -*-
from datetime import datetime
import requests

class MemoryCache(object):
    def __init__(self, location='memory', *args, **kwargs):
        self.responses = {}
        self.url_map = {}

    def save_response(self, url, response):
        self.responses[url] = response, datetime.now()
        self.url_map[url] = response.url
        for r in response.history:
            self.url_map[r.url] = response.url

    def get_response_and_time(self, url, default=(None, None)):
        try:
            return self.responses[self.url_map[url]]
        except KeyError:
            return default

    def del_cached_url(self, url):
        try:
            response, _ = self.responses[url]
            for r in response.history:
                del self.url_map[r.url]
            del self.url_map[url]
            del self.responses[url]
        except KeyError:
            pass

    def clear(self):
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