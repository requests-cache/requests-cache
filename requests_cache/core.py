#!/usr/bin/env python
# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from requests.sessions import Session
from requests import Request

from requests_cache import backends


_original_session_request = Session.request
_original_request_send = Request.send
_config = {}
_cache = None


def configure(cache_filename_prefix='cache', backend='sqlite', expire_after=60,
              allowable_codes=(200,), monkey_patch=True):
    try:
        global _cache
        _cache = backends.registry[backend](cache_filename_prefix)
    except KeyError:
        raise ValueError('Unsupported backend "%s" try one of: %s' %
                         (backend, ', '.join(backends.registry.keys())))
    if monkey_patch:
        redo_patch()
    _config['expire_after'] = expire_after
    _config['allowable_codes'] = allowable_codes


def clear():
    _cache.clear()


def undo_patch():
    Session.request = _original_session_request
    Request.send = _original_request_send


def redo_patch():
    Session.request = _session_request_hook
    Request.send = _request_send_hook


def get_cache():
    return _cache


def dummy_send(*args, **kwargs):
    return True

def _session_request_hook(self, method, url, **kwargs):
    print method, url, kwargs
    if not kwargs.get('return_response', True):  # Used in async
        return _original_session_request(self, method, url, **kwargs)
    response, timestamp = _cache.get_response_and_time(url)
    if response is None:
        response = _original_session_request(self, method, url, **kwargs)
        if response.status_code in _config['allowable_codes']:
            _cache.save_response(response.url, response)
        return response
    difference = datetime.now() - timestamp
    if difference > timedelta(minutes=_config['expire_after']):
        _cache.del_cached_url(url)
    return response

def _request_send_hook(self, anyway=False, prefetch=False):
    print 'send', self, self.url, anyway, prefetch
    return _original_request_send(self, anyway, prefetch)
