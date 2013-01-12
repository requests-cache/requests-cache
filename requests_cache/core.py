#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    requests_cache.core
    ~~~~~~~~~~~~~~~~~~~

    Core functions for configuring cache and monkey patching ``requests``
"""
from contextlib import contextmanager
from datetime import datetime, timedelta

import requests
from requests import Session

from requests_cache import backends
from requests_cache.compat import str



class CachedSession(Session):
    def __init__(self, cache_name='cache', backend='sqlite', expire_after=None,
                 allowable_codes=(200,), allowable_methods=('GET',),
                 monkey_patch=True, **backend_options):
        """
        Configure cache storage and patch ``requests`` library to transparently cache responses
        :param cache_name: for ``sqlite`` backend: cache file will start with this prefix,
                           e.g ``cache.sqlite``
                           for ``mongodb``: it's used as database name
        :param backend: cache backend e.g ``'sqlite'``, ``'mongodb'``, ``'memory'``.
                        See :ref:`persistence`
        :param expire_after: number of seconds after cache will be expired
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
            self.cache = backends.registry[backend](cache_name, **backend_options)
        except KeyError:
            raise ValueError('Unsupported backend "%s" try one of: %s' %
                             (backend, ', '.join(backends.registry.keys())))

        self._cache_expire_after = expire_after
        self._cache_allowable_codes = allowable_codes
        self._cache_allowable_methods = allowable_methods
        super(CachedSession, self).__init__()



    def send(self, request, **kwargs):
        if request.method not in self._cache_allowable_methods:
            return super(CachedSession, self).send(request, **kwargs)

        if request.method == 'POST':
            data = self._encode_params(getattr(request, 'data', {}))
            if isinstance(data, tuple):  # old requests versions
                data = data[1]
            cache_url = request.url + str(data)
        else:
            cache_url = request.url

        def send_request_and_cache_response():
            response = super(CachedSession, self).send(request, **kwargs)
            if response.status_code in self._cache_allowable_codes:
                self.cache.save_response(cache_url, response)
            response.from_cache = False
            return response

        response, timestamp = self.cache.get_response_and_time(cache_url)
        if response is None:
            return send_request_and_cache_response()

        if self._cache_expire_after is not None:
            difference = datetime.now() - timestamp
            if difference > timedelta(seconds=self._cache_expire_after):
                self.cache.del_cached_url(cache_url)
                return send_request_and_cache_response()

        response.from_cache = True
        return response


def install_cached_session(session_factory=CachedSession):
    requests.sessions.Session = session_factory


def configure(*args, **kwargs):
    install_cached_session(lambda : CachedSession(*args, **kwargs))
