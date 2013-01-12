#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    requests_cache.core
    ~~~~~~~~~~~~~~~~~~~

    Core functions for configuring cache and monkey patching ``requests``
"""
from datetime import datetime, timedelta

import requests
from requests import Session

from requests_cache import backends
from requests_cache.compat import str, basestring


class CachedSession(Session):
    def __init__(self, cache_name='cache', backend='sqlite', expire_after=None,
                 allowable_codes=(200,), allowable_methods=('GET',),
                 monkey_patch=True, **backend_options):
        """
        Configure cache storage and patch ``requests`` library to transparently cache responses
        :param cache_name: for ``sqlite`` backend: cache file will start with this prefix,
                           e.g ``cache.sqlite``
                           for ``mongodb``: it's used as database name
        :param backend: cache backend name e.g ``'sqlite'``, ``'mongodb'``, ``'memory'``.
                        Or instance of backend implementation. See :ref:`persistence`
        :param expire_after: number of seconds after cache will be expired
                             or `None` (default) to ignore expiration
        :type expire_after: float
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
        if isinstance(backend, basestring):
            try:
                self.cache = backends.registry[backend](cache_name, **backend_options)
            except KeyError:
                raise ValueError('Unsupported backend "%s" try one of: %s' %
                                 (backend, ', '.join(backends.registry.keys())))
        else:
            self.cache = backend

        self._cache_expire_after = expire_after
        self._cache_allowable_codes = allowable_codes
        self._cache_allowable_methods = allowable_methods
        super(CachedSession, self).__init__()

    def send(self, request, **kwargs):
        if request.method not in self._cache_allowable_methods:
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
            difference = datetime.now() - timestamp
            if difference > timedelta(seconds=self._cache_expire_after):
                self.cache.delete(cache_key)
                return send_request_and_cache_response()

        response.from_cache = True
        return response

    def request(self, method, url, params=None, data=None, headers=None,
                cookies=None, files=None, auth=None, timeout=None,
                allow_redirects=True, proxies=None, hooks=None, stream=None,
                verify=None, cert=None):
        response = super(CachedSession, self).request(method, url, params, data,
                                                      headers, cookies, files,
                                                      auth, timeout,
                                                      allow_redirects, proxies,
                                                      hooks, stream, verify, cert)
        main_key = self.cache.create_key(response.request)
        for r in response.history:
            self.cache.add_key_mapping(
                self.cache.create_key(r.request), main_key
            )
        return response


def install_cached_session(session_factory=CachedSession):
    requests.sessions.Session = session_factory


def configure(*args, **kwargs):
    install_cached_session(lambda : CachedSession(*args, **kwargs))
