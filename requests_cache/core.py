"""
    requests_cache.core
    ~~~~~~~~~~~~~~~~~~~

    Core functions for configuring cache and monkey patching ``requests``
"""
from contextlib import contextmanager
from datetime import datetime, timedelta
from operator import itemgetter
from typing import Callable, Iterable, Union

import requests
from requests import Session as OriginalSession
from requests.hooks import dispatch_hook

from . import backends


class CachedSession(OriginalSession):
    """Requests ``Sessions`` with caching support

    Args:
        cache_name: Cache prefix or namespace, depending on backend; see notes below
        backend: Cache backend name; one of ``['sqlite', 'mongodb', 'gridfs', 'redis', 'dynamodb', 'memory']``.
                Default behavior is to use ``'sqlite'`` if available, otherwise fallback to ``'memory'``.
        expire_after: Number of seconds after which a cache entry will expire; set to ``None`` to
            never expire
        allowable_codes: Only cache responses with one of these codes
        allowable_methods: Cache only responses for one of these HTTP methods
        include_headers: Make request headers part of the cache key
        ignored_parameters: List of request parameters to be excluded from the cache key.
        filter_fn: function that takes a :py:class:`aiohttp.ClientResponse` object and
            returns a boolean indicating whether or not that response should be cached. Will be
            applied to both new and previously cached responses
        old_data_on_error: Return expired cached responses if new request fails

    The ``cache_name`` parameter will be used as follows depending on the backend:

        * ``sqlite``: Cache filename prefix, e.g ``my_cache.sqlite``
        * ``mongodb``: Database name
        * ``redis``: Namespace, meaning all keys will be prefixed with ``'cache_name:'``

    Note on cache key parameters: Set ``include_get_headers=True`` if you want responses to be
    cached under different keys if they only differ by headers. You may also provide
    ``ignored_parameters`` to ignore specific request params. This is useful, for example, when
    requesting the same resource with different credentials or access tokens.
    """

    def __init__(
        self,
        cache_name: str = 'cache',
        backend: str = None,
        expire_after: Union[int, float, timedelta] = None,
        allowable_codes: Iterable[int] = (200,),
        allowable_methods: Iterable['str'] = ('GET',),
        filter_fn: Callable = None,
        old_data_on_error: bool = False,
        **backend_options
    ):
        self.cache = backends.create_backend(backend, cache_name, backend_options)
        self._cache_name = cache_name

        if expire_after is not None and not isinstance(expire_after, timedelta):
            expire_after = timedelta(seconds=expire_after)
        self._cache_expire_after = expire_after

        self._cache_allowable_codes = allowable_codes
        self._cache_allowable_methods = allowable_methods
        self._filter_fn = filter_fn or (lambda r: True)
        self._return_old_data_on_error = old_data_on_error
        self._is_cache_disabled = False
        super(CachedSession, self).__init__()

    def send(self, request, **kwargs):
        if self._is_cache_disabled or request.method not in self._cache_allowable_methods:
            response = super(CachedSession, self).send(request, **kwargs)
            response.from_cache = False
            response.cache_date = None
            return response

        cache_key = self.cache.create_key(request)

        def send_request_and_cache_response():
            response = super(CachedSession, self).send(request, **kwargs)
            if response.status_code in self._cache_allowable_codes:
                self.cache.save_response(cache_key, response)
            response.from_cache = False
            response.cache_date = None
            return response

        try:
            response, timestamp = self.cache.get_response_and_time(cache_key)
        except (ImportError, TypeError):
            return send_request_and_cache_response()

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
        response.cache_date = timestamp
        response = dispatch_hook('response', request.hooks, response, **kwargs)
        return response

    def request(self, method, url, params=None, data=None, **kwargs):
        response = super(CachedSession, self).request(
            method, url, _normalize_parameters(params), _normalize_parameters(data), **kwargs
        )
        if self._is_cache_disabled:
            return response

        main_key = self.cache.create_key(response.request)

        # If self._return_old_data_on_error is set,
        # responses won't always have the from_cache attribute.
        if hasattr(response, "from_cache") and not response.from_cache and self._filter_fn(response) is not True:
            self.cache.delete(main_key)
            return response

        for r in response.history:
            self.cache.add_key_mapping(self.cache.create_key(r.request), main_key)
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
        """Removes expired responses from storage"""
        if not self._cache_expire_after:
            return
        self.cache.remove_old_entries(datetime.utcnow() - self._cache_expire_after)

    def __repr__(self):
        return "<CachedSession(%s('%s', ...), expire_after=%s, " "allowable_methods=%s)>" % (
            self.cache.__class__.__name__,
            self._cache_name,
            self._cache_expire_after,
            self._cache_allowable_methods,
        )


def install_cache(
    cache_name: str = 'cache',
    backend: str = None,
    expire_after: Union[int, float, timedelta] = None,
    allowable_codes: Iterable[int] = (200,),
    allowable_methods: Iterable['str'] = ('GET',),
    filter_fn: Callable = None,
    old_data_on_error: bool = False,
    session_factory=CachedSession,
    **backend_options
):
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
                filter_fn=filter_fn,
                old_data_on_error=old_data_on_error,
                **backend_options
            )

    _patch_session_factory(_ConfiguredCachedSession)


def uninstall_cache():
    """Restores ``requests.Session`` and disables cache"""
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
    """Returns internal cache object from globally installed ``CachedSession``"""
    return requests.Session().cache


def clear():
    """Clears globally installed cache"""
    get_cache().clear()


def remove_expired_responses():
    """Removes expired responses from storage"""
    return requests.Session().remove_expired_responses()


def _patch_session_factory(session_factory=CachedSession):
    requests.Session = requests.sessions.Session = session_factory


def _normalize_parameters(params):
    """If builtin dict is passed as parameter, returns sorted list
    of key-value pairs
    """
    if type(params) is dict:
        return sorted(params.items(), key=itemgetter(0))
    return params
