#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    requests_cache.core
    ~~~~~~~~~~~~~~~~~~~

    Core functions for configuring cache and monkey patch ``requests.Request.send``
"""
from datetime import datetime, timedelta

from requests import Request
from requests.hooks import dispatch_hook

from requests_cache import backends


_original_request_send = Request.send
_config = {}
_cache = None


def configure(cache_filename_prefix='cache', backend='sqlite', expire_after=60,
              allowable_codes=(200,), monkey_patch=True):
    """ Configure cache and patch ``requests`` library, to  transparently use it

    :param cache_filename_prefix: cache files will start with this prefix,
                                  e.g ``cache_urls.sqlite``, ``cache_responses.sqlite``
    :param backend: cache backend e.g ``'sqlite'``, ``'memory'``
    :param expire_after: number of minutes after cache will be expired
    :type expire_after: int or float
    :param allowable_codes: limit caching only for response with this codes
    :type allowable_codes: tuple
    :param monkey_patch: patch ``requests.Request.send`` if True, otherwise
                         cache will not work until calling :func:`redo_patch`
    """
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
    """ Clear cache
    """
    _cache.clear()


def undo_patch():
    """ Undo ``requests`` monkey patch
    """
    Request.send = _original_request_send


def redo_patch():
    """ Redo ``requests`` monkey patch
    """
    Request.send = _request_send_hook


def get_cache():
    """ Returns internal cache object
    """
    return _cache

def delete_url(url):
    """ Deletes all cache for `url`
    """
    _cache.del_cached_url(url)


def _request_send_hook(self, *args, **kwargs):
    #print('send: %s' % self.url)
    response, timestamp = _cache.get_response_and_time(self.url)
    if response is None:
        result = _original_request_send(self, *args, **kwargs)
        if result and self.response.status_code in _config['allowable_codes']:
            _cache.save_response(self.response.url, self.response)
        return result
    self.sent = True
    difference = datetime.now() - timestamp
    if difference > timedelta(minutes=_config['expire_after']):
        _cache.del_cached_url(self.url)
    self.response = response
    # TODO is it stable api?
    dispatch_hook('response', self.hooks, self.response)
    r = dispatch_hook('post_request', self.hooks, self)
    self.__dict__.update(r.__dict__)
    return True

