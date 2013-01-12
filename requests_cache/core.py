#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    requests_cache.core
    ~~~~~~~~~~~~~~~~~~~

    Core functions for configuring cache and monkey patching ``requests``
"""
from contextlib import contextmanager
from datetime import datetime, timedelta

from requests import Session

from requests_cache import backends
from requests_cache.compat import str


_original_request_send = Session.send
_config = {}
_cache = None


def configure(cache_name='cache', backend='sqlite', expire_after=None,
              allowable_codes=(200,), allowable_methods=('GET',),
              monkey_patch=True, **backend_options):
    """
    Configure cache storage and patch ``requests`` library to transparently cache responses
    :param cache_name: for ``sqlite`` backend: cache file will start with this prefix,
                       e.g ``cache.sqlite``
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
    :param monkey_patch: patch ``requests.Session.send`` if `True` (default), otherwise
                         cache will not work until calling :func:`redo_patch`
                         or using :func:`enabled` context manager
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
    previous = Session.send
    undo_patch()
    try:
        yield
    finally:
        Session.send = previous

@contextmanager
def enabled():
    """
    Context manager for temporary enabling cache
    ::

        >>> with requests_cache.enabled():
        ...     request.get('http://httpbin.org/ip')
        ...     request.get('http://httpbin.org/get')

    """
    previous = Session.send
    redo_patch()
    try:
        yield
    finally:
        Session.send = previous

def clear():
    """ Clear cache
    """
    _cache.clear()


def undo_patch():
    """ Undo ``requests`` monkey patch
    """
    Session.send = _original_request_send


def redo_patch():
    """ Redo ``requests`` monkey patch
    """
    Session.send = _request_send_hook


def get_cache():
    """ Returns internal cache object
    """
    return _cache


def delete_url(url):
    """ Deletes all cache for `url`
    """
    _cache.del_cached_url(url)


def _request_send_hook(self, request, *args, **kwargs):
    if request.method not in _config['allowable_methods']:
        return _original_request_send(self, request, *args, **kwargs)

    if request.method == 'POST':
        data = self._encode_params(getattr(request, 'data', {}))
        if isinstance(data, tuple):  # old requests versions
            data = data[1]
        cache_url = request.url + str(data)
    else:
        cache_url = request.url

    def send_request_and_cache_response():
        response = _original_request_send(self, request, *args, **kwargs)
        if response.status_code in _config['allowable_codes']:
            _cache.save_response(cache_url, response)
        return response

    response, timestamp = _cache.get_response_and_time(cache_url)
    if response is None:
        return send_request_and_cache_response()

    if _config['expire_after'] is not None:
        difference = datetime.now() - timestamp
        if difference > timedelta(minutes=_config['expire_after']):
            _cache.del_cached_url(cache_url)
            return send_request_and_cache_response()

    response.from_cache = True
    return response
