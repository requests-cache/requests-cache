#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests

from requests_cache.backends.dbdict import DbPickleDict
from requests_cache.backends.base import MemoryCache, reduce_response, restore_response


class DbCache(MemoryCache):

    def __init__(self, location='cache', *args, **kwargs):
        super(DbCache, self).__init__(*args, **kwargs)
        self.url_map = DbPickleDict('%s_urls' % location)
        self.responses = DbPickleDict('%s_responses' % location)

    def save_response(self, url, response):
        response = reduce_response(response)
        super(DbCache, self).save_response(url, response)

    def get_response_and_time(self, url, default=(None, None)):
        response, timestamp = super(DbCache, self).get_response_and_time(url)
        if response is None:
            return default
        response = restore_response(response)
        return response, timestamp

