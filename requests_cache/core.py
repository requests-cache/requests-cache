#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    requests_cache.core
    ~~~~~~~~~~~~~~~~~~~

    Core functions for configuring cache and monkey patching ``requests``
"""
from contextlib import contextmanager
from datetime import datetime, timedelta
from time import sleep

from requests import Request
try:
    from requests.hooks import dispatch_hook
except ImportError:
    dispatch_hook = None

from requests_cache import backends
from requests_cache.compat import urlencode


_original_request_send = Request.send
_config = {}
_cache = None


def configure(cache_name='cache', backend='sqlite', expire_after=None,
              allowable_codes=(200,), allowable_methods=('GET',),
              monkey_patch=True, wait = None, **backend_options):
    """
    Configure cache storage and patch ``requests`` library to transparently cache responses

    :param cache_name: for ``sqlite`` backend: cache files will start with this prefix,
                       e.g ``cache_urls.sqlite``, ``cache_responses.sqlite``

                       for ``mongodb``: it's used as database name
    :param backend: cache backend e.g ``'sqlite'``, ``'mongodb'``, ``'memory'``.
                    See :ref:`persistence`
    :param expire_after: number of minutes after cache will be expired
                         or `None` (default) to ignore expiration
    :type expire_after: int, float or None
    :param allowable_codes: limit caching only for response with this codes (default: 200)
    :type allowable_codes: tuple
    :param allowable_methods: cache only requests of this methods (default: 'GET')
    :type allowable_methods: tuple
    :param monkey_patch: patch ``requests.Request.send`` if `True` (default), otherwise
                         cache will not work until calling :func:`redo_patch`
    :param sleep: the time to wait between two requests (default: None)
    :kwarg backend_options: options for chosen backend. See corresponding
                            :ref:`sqlite <backends_sqlite>` and :ref:`mongo <backends_mongo>` backends API documentation
    """
    try:
        global _cache
        _cache = backends.registry[backend](cache_name, **backend_options)
    except KeyError:
        raise ValueError('Unsupported backend "%s" try one of: %s' %
                         (backend, ', '.join(backends.registry.keys())))
    if monkey_patch:
        redo_patch()
    _config['expire_after'] = expire_after
    _config['allowable_codes'] = allowable_codes
    _config['allowable_methods'] = allowable_methods
    _config['wait'] = wait


def has_url(url):
    """ Returns `True` if cache has `url`, `False` otherwise
    """
    return _cache.has_url(url)

@contextmanager
def disabled():
    """
    Context manager for temporary disabling cache
    ::

        >>> with requests_cache.disabled():
        ...     request.get('http://httpbin.org/ip')
        ...     request.get('http://httpbin.org/get')

    """
    previous = Request.send
    undo_patch()
    try:
        yield
    finally:
        Request.send = previous

@contextmanager
def enabled():
    """
    Context manager for temporary enabling cache
    ::

        >>> with requests_cache.enabled():
        ...     request.get('http://httpbin.org/ip')
        ...     request.get('http://httpbin.org/get')

    """
    previous = Request.send
    redo_patch()
    try:
        yield
    finally:
        Request.send = previous

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


# TODO make it possible to check if response is taken from cache
def _request_send_hook(self, *args, **kwargs):
    if self.method not in _config['allowable_methods']:
        return _original_request_send(self, *args, **kwargs)

    if self.method == 'POST':
        cache_url = self.full_url + urlencode(getattr(self, 'data', {}))
    else:
        cache_url = self.full_url

    def send_request_and_cache_response():
        result = _original_request_send(self, *args, **kwargs)
        if result and self.response.status_code in _config['allowable_codes']:
            _cache.save_response(cache_url, self.response)
            if _config['wait']: sleep( _config['wait'] )
        return result

    response, timestamp = _cache.get_response_and_time(cache_url)
    if response is None:
        return send_request_and_cache_response()

    if _config['expire_after'] is not None:
        difference = datetime.now() - timestamp
        if difference > timedelta(minutes=_config['expire_after']):
            _cache.del_cached_url(cache_url)
            return send_request_and_cache_response()

    self.sent = True
    self.response = response
    # TODO: is it stable api?
    if dispatch_hook is not None:
        dispatch_hook('response', self.hooks, self.response)
        r = dispatch_hook('post_request', self.hooks, self)
        self.__dict__.update(r.__dict__)
    return True
