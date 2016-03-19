#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    requests_cache.core
    ~~~~~~~~~~~~~~~~~~~

    Core functions for configuring cache and monkey patching ``requests``
"""
from contextlib import contextmanager
from datetime import datetime, timedelta
from operator import itemgetter

import requests
from requests import Session as OriginalSession
from requests.hooks import dispatch_hook

from requests_cache import backends
from requests_cache.compat import basestring

try:
    ver = tuple(map(int, requests.__version__.split(".")))
except ValueError:
    pass
else:
    # We don't need to dispatch hook in Requests <= 1.1.0
    if ver < (1, 2, 0):
        dispatch_hook = lambda key, hooks, hook_data, *a, **kw: hook_data
    del ver


class CachedSession(OriginalSession):
    """ Requests ``Sessions`` with caching support.
    """

    def __init__(self, cache_name='cache', backend=None, expire_after=None,
                 allowable_codes=(200,), allowable_methods=('GET',),
                 old_data_on_error=False, **backend_options):
        """
        :param cache_name: for ``sqlite`` backend: cache file will start with this prefix,
                           e.g ``cache.sqlite``

                           for ``mongodb``: it's used as database name
                           
                           for ``redis``: it's used as the namespace. This means all keys
                           are prefixed with ``'cache_name:'``
        :param backend: cache backend name e.g ``'sqlite'``, ``'mongodb'``, ``'redis'``, ``'memory'``.
                        (see :ref:`persistence`). Or instance of backend implementation.
                        Default value is ``None``, which means use ``'sqlite'`` if available,
                        otherwise fallback to ``'memory'``.
        :param expire_after: ``timedelta`` or number of seconds after cache will be expired
                             or `None` (default) to ignore expiration
        :type expire_after: float
        :param allowable_codes: limit caching only for response with this codes (default: 200)
        :type allowable_codes: tuple
        :param allowable_methods: cache only requests of this methods (default: 'GET')
        :type allowable_methods: tuple
        :kwarg backend_options: options for chosen backend. See corresponding
                                :ref:`sqlite <backends_sqlite>`, :ref:`mongo <backends_mongo>` 
                                and :ref:`redis <backends_redis>` backends API documentation
        :param include_get_headers: If `True` headers will be part of cache key.
                                    E.g. after get('some_link', headers={'Accept':'application/json'})
                                    get('some_link', headers={'Accept':'application/xml'}) is not from cache.
        :param ignored_parameters: List of parameters to be excluded from the cache key.
                                   Useful when requesting the same resource through different
                                   credentials or access tokens, passed as parameters.
        :param old_data_on_error: If `True` it will return expired cached response if update fails
        """
        self.cache = backends.create_backend(backend, cache_name, backend_options)
        self._cache_name = cache_name

        if expire_after is not None and not isinstance(expire_after, timedelta):
            expire_after = timedelta(seconds=expire_after)
        self._cache_expire_after = expire_after

        self._cache_allowable_codes = allowable_codes
        self._cache_allowable_methods = allowable_methods
        self._return_old_data_on_error = old_data_on_error
        self._is_cache_disabled = False
        super(CachedSession, self).__init__()

    def send(self, request, **kwargs):
        if (self._is_cache_disabled
            or request.method not in self._cache_allowable_methods):
            response = super(CachedSession, self).send(request, **kwargs)
            response.from_cache = False
            return response

        cache_key = self.cache.create_key(request)

        def send_request_and_cache_response():
            response = super(CachedSession, self).send(request, **kwargs)
            if response.status_code in self._cache_allowable_codes:
                self.cache.save_response(cache_key, response)
            response.from_cache = False
            return response

        response, timestamp = self.cache.get_response_and_time(cache_key)
        if response is None:
            return send_request_and_cache_response()

        if self._cache_expire_after is not None:
            is_expired = datetime.utcnow() - timestamp > self._cache_expire_after
            if is_expired:
                if not self._return_old_data_on_error:
                    self.cache.delete(cache_key)
                    return send_request_and_cache_response()
                try:
                    new_response = send_request_and_cache_response()
                except Exception:
                    return response
                else:
                    if new_response.status_code not in self._cache_allowable_codes:
                        return response
                    return new_response

        # dispatch hook here, because we've removed it before pickling
        response.from_cache = True
        response = dispatch_hook('response', request.hooks, response, **kwargs)
        return response

    def request(self, method, url, params=None, data=None, **kwargs):
        response = super(CachedSession, self).request(
            method, url,
            _normalize_parameters(params),
            _normalize_parameters(data),
            **kwargs
        )
        if self._is_cache_disabled:
            return response

        main_key = self.cache.create_key(response.request)
        for r in response.history:
            self.cache.add_key_mapping(
                self.cache.create_key(r.request), main_key
            )
        return response

    @contextmanager
    def cache_disabled(self):
        """
        Context manager for temporary disabling cache
        ::

            >>> s = CachedSession()
            >>> with s.cache_disabled():
            ...     s.get('http://httpbin.org/ip')
        """
        self._is_cache_disabled = True
        try:
            yield
        finally:
            self._is_cache_disabled = False

    def remove_expired_responses(self):
        """ Removes expired responses from storage
        """
        if not self._cache_expire_after:
            return
        self.cache.remove_old_entries(datetime.utcnow() - self._cache_expire_after)

    def __repr__(self):
        return (
            "<CachedSession(%s('%s', ...), expire_after=%s, "
            "allowable_methods=%s)>" % (
                self.cache.__class__.__name__, self._cache_name,
                self._cache_expire_after, self._cache_allowable_methods
            )
        )


def install_cache(cache_name='cache', backend=None, expire_after=None,
                  allowable_codes=(200,), allowable_methods=('GET',),
                  session_factory=CachedSession, **backend_options):
    """
    Installs cache for all ``Requests`` requests by monkey-patching ``Session``

    Parameters are the same as in :class:`CachedSession`. Additional parameters:

    :param session_factory: Session factory. It must be class which inherits :class:`CachedSession` (default)
    """
    if backend:
        backend = backends.create_backend(backend, cache_name, backend_options)

    class _ConfiguredCachedSession(session_factory):
        def __init__(self):
            super(_ConfiguredCachedSession, self).__init__(
                cache_name=cache_name,
                backend=backend,
                expire_after=expire_after,
                allowable_codes=allowable_codes,
                allowable_methods=allowable_methods,
                **backend_options
            )

    _patch_session_factory(_ConfiguredCachedSession)


# backward compatibility
configure = install_cache


def uninstall_cache():
    """ Restores ``requests.Session`` and disables cache
    """
    _patch_session_factory(OriginalSession)


@contextmanager
def disabled():
    """
    Context manager for temporary disabling globally installed cache

    .. warning:: not thread-safe

    ::

        >>> with requests_cache.disabled():
        ...     requests.get('http://httpbin.org/ip')
        ...     requests.get('http://httpbin.org/get')

    """
    previous = requests.Session
    uninstall_cache()
    try:
        yield
    finally:
        _patch_session_factory(previous)


@contextmanager
def enabled(*args, **kwargs):
    """
    Context manager for temporary installing global cache.

    Accepts same arguments as :func:`install_cache`

    .. warning:: not thread-safe

    ::

        >>> with requests_cache.enabled('cache_db'):
        ...     requests.get('http://httpbin.org/get')

    """
    install_cache(*args, **kwargs)
    try:
        yield
    finally:
        uninstall_cache()


def get_cache():
    """ Returns internal cache object from globally installed ``CachedSession``
    """
    return requests.Session().cache


def clear():
    """ Clears globally installed cache
    """
    get_cache().clear()


def remove_expired_responses():
    """ Removes expired responses from storage
    """
    return requests.Session().remove_expired_responses()


def _patch_session_factory(session_factory=CachedSession):
    requests.Session = requests.sessions.Session = session_factory


def _normalize_parameters(params):
    """ If builtin dict is passed as parameter, returns sorted list
    of key-value pairs
    """
    if type(params) is dict:
        return sorted(params.items(), key=itemgetter(0))
    return params
