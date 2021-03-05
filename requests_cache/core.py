"""
    requests_cache.core
    ~~~~~~~~~~~~~~~~~~~

    Core functions for configuring cache and monkey patching ``requests``
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from operator import itemgetter
from typing import Callable, Iterable, Union

import requests
from requests import Session as OriginalSession
from requests.hooks import dispatch_hook

from requests_cache.backends.base import BACKEND_KWARGS

from . import backends


class CacheMixin:
    """Mixin class that extends ``requests.Session`` with caching features.

    Args:
        cache_name: Cache prefix or namespace, depending on backend; see notes below
        backend: Cache backend name; one of ``['sqlite', 'mongodb', 'gridfs', 'redis', 'dynamodb', 'memory']``.
                Default behavior is to use ``'sqlite'`` if available, otherwise fallback to ``'memory'``.
        expire_after: Number of seconds after which a cache entry will expire; set to ``None`` to
            never expire
        allowable_codes: Only cache responses with one of these codes
        allowable_methods: Cache only responses for one of these HTTP methods
        include_get_headers: Make request headers part of the cache key
        ignored_parameters: List of request parameters to be excluded from the cache key.
        filter_fn: function that takes a :py:class:`aiohttp.ClientResponse` object and
            returns a boolean indicating whether or not that response should be cached. Will be
            applied to both new and previously cached responses
        old_data_on_error: Return expired cached responses if new request fails

    See individual backend classes for additional backend-specific arguments.

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
        **kwargs
    ):
        self.cache = backends.create_backend(backend, cache_name, kwargs)
        self._cache_name = cache_name

        if expire_after is not None and not isinstance(expire_after, timedelta):
            expire_after = timedelta(seconds=expire_after)
        self._cache_expire_after = expire_after

        self._cache_allowable_codes = allowable_codes
        self._cache_allowable_methods = allowable_methods
        self._filter_fn = filter_fn or (lambda r: True)
        self._return_old_data_on_error = old_data_on_error
        self._is_cache_disabled = False

        # Remove any requests-cache-specific kwargs before passing along to superclass
        session_kwargs = {k: v for k, v in kwargs.items() if k not in BACKEND_KWARGS}
        super().__init__(**session_kwargs)

    def _determine_expiration_datetime(self, response, relative_to=None):
        """Determines the absolute expiration datetime for a response.
        Requires :attr:`self._cache_expire_after` and :attr:`self._request_expire_after` to be set.
        See :meth:`request` for more information.

        :param response: the response (potentially loaded from the cache)
        :type response: requests.Response
        :param relative_to: Parameter for easy unit testing to fix ``now``,
                            defaults to ``datetime.now(timezone.utc)`` for normal use.
        :type relative_to: Union[None, datetime.datetime]
        :return: The absolute expiration date
        :rtype: datetime.datetime
        """
        now = datetime.now(timezone.utc) if relative_to is None else relative_to

        cache_expire_after = self._cache_expire_after
        request_expire_after = self._request_expire_after
        response_expire_after = getattr(response, 'expire_after', 'default')

        def to_absolute(expire_after):
            if expire_after is None:
                return None
            if isinstance(expire_after, timedelta):
                return now + expire_after
            if isinstance(expire_after, datetime):
                return expire_after
            return now + timedelta(seconds=expire_after)

        if request_expire_after == 'cached' and response_expire_after not in ['cached', 'default']:
            return to_absolute(response_expire_after)
        if request_expire_after in ['default', 'cached']:
            return to_absolute(cache_expire_after)
        return to_absolute(request_expire_after)

    def send(self, request, **kwargs):
        do_not_cache = (
            self._is_cache_disabled
            or request.method not in self._cache_allowable_methods
            or self._request_expire_after is None
        )
        if do_not_cache:
            response = super().send(request, **kwargs)
            response.from_cache = False
            response.cache_date = None
            response.expiration_date = None
            response.expire_after = 'default'
            return response

        cache_key = self.cache.create_key(request)

        try:
            response, timestamp = self.cache.get_response_and_time(cache_key)
        except (ImportError, TypeError):
            response, timestamp = None, None

        if response is None:
            return self.send_request_and_cache_response(request, cache_key, **kwargs)

        if getattr(response, 'expiration_date', None) is not None:
            now = datetime.now(timezone.utc)
            is_expired = now > response.expiration_date
        else:
            is_expired = False

        cache_invalid = response.expire_after != self._request_expire_after and self._request_expire_after != 'default'
        if cache_invalid or is_expired:
            if not self._return_old_data_on_error:
                self.cache.delete(cache_key)
                return self.send_request_and_cache_response(request, cache_key, **kwargs)
            try:
                new_response = self.send_request_and_cache_response(request, cache_key, **kwargs)
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

    def request(self, method, url, params=None, data=None, expire_after='default', **kwargs):
        """This method prepares and sends a request while automatically
        performing any necessary caching operations.

        If a cache is installed, whenever a standard ``requests`` function is
        called, e.g. :func:`requests.get`, this method is called to handle caching
        and calling the original :func:`requests.request` method.

        This method adds an additional keyword argument to :func:`requests.request`, ``expire_after``.
        It is used to set the expiry time for a specific request to override
        the cache default, and can be omitted on subsequent calls. Subsequent
        calls with different values invalidate the cache, calls with the same values (or without any values) don't.

        Given

        - the `expire_after` from the installed cache (the ``'default'``)
        - the `expire_after` passed to an individual request
        - the `expire_after` stored inside the cache (the ``'cached'`` value)

        the following rules hold for which `expire_after` is used:

        +-----------------------------------+----------------------------------------------+
        |                       |           | request(..., expire_after=X)                 |
        +=======================+===========+===============+===============+==============+
        |                       |           | 'default'     | 'cached'      | other        |
        +-----------------------+-----------+---------------+---------------+--------------+
        | response.expire_after | 'default' | cache default | cache default | from request |
        |                       +-----------+---------------+---------------+--------------+
        |                       | 'cached'  | cache default | cache default | from request |
        |                       +-----------+---------------+---------------+--------------+
        |                       | other     | cache default | from response | from request |
        +-----------------------+-----------+---------------+---------------+--------------+

        That is, if the request's ``expire_after`` is set to ``'default'``
        (which is the default value) the default caching behavior is used.

        If the request's ``expire_after`` is set to ``'cached'``, the value from
        the response (potentially stored inside the cache) will be used, unless
        that one is 'default' or 'cached', in which case the default cache
        behavior will be used.

        .. note::
            Setting ``expire_after`` to ``'cached'`` usually leads to unexpected results,
            as it recalculates the expiration date from a cached value.

        Whenever the request's expire_after is anything else (a number, None,
        datetime, or timedelta), that value will be used.

        In all cases, if the value is an explicit datetime it returned as is.
        If it is None, it is also returned as is and caches forever.
        All other values will be considered a relative time in the future.

        :param expire_after: Specifies when the cache for a particular response
                             expires. Accepts multiple argument types:

                             - ``'default'`` to use the default expiry from the installed cache. This is the default.
                             - ``'cached'`` to use the expiry from the stored response cache.
                             - :const:`None` to disable caching for this request
                             - :class:`~datetime.timedelta` to set relative expiry times
                             - :class:`float` values as time in seconds for :class:`~datetime.timedelta`
                             - :class:`~datetime.datetime` to set an explicit expiration date

        :type expire_after: Union[None, str, float, datetime.timedelta, datetime.datetime]
        """
        self._request_expire_after = expire_after  # store expire_after so we can handle it in the send-method
        response = super().request(method, url, _normalize_parameters(params), _normalize_parameters(data), **kwargs)

        if self._is_cache_disabled:
            try:
                return response
            finally:
                self._request_expire_after = 'default'

        main_key = self.cache.create_key(response.request)

        # If self._return_old_data_on_error is set,
        # responses won't always have the from_cache attribute.
        if hasattr(response, "from_cache") and not response.from_cache and self._filter_fn(response) is not True:
            self.cache.delete(main_key)
            try:
                return response
            finally:
                self._request_expire_after = 'default'

        for r in response.history:
            self.cache.add_key_mapping(self.cache.create_key(r.request), main_key)
        try:
            return response
        finally:
            self._request_expire_after = 'default'

    def send_request_and_cache_response(self, request, cache_key, **kwargs):
        response = super().send(request, **kwargs)
        if response.status_code in self._cache_allowable_codes:
            response.expire_after = self._request_expire_after
            response.expiration_date = self._determine_expiration_datetime(response)
            self.cache.save_response(cache_key, response)
        response.from_cache = False
        response.cache_date = None
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
        self.cache.remove_old_entries(datetime.now(timezone.utc))

    def __repr__(self):
        return "<CachedSession(%s('%s', ...), expire_after=%s, " "allowable_methods=%s)>" % (
            self.cache.__class__.__name__,
            self._cache_name,
            self._cache_expire_after,
            self._cache_allowable_methods,
        )


class CachedSession(CacheMixin, OriginalSession):
    pass


def install_cache(
    cache_name: str = 'cache',
    backend: str = None,
    expire_after: Union[int, float, timedelta] = None,
    allowable_codes: Iterable[int] = (200,),
    allowable_methods: Iterable['str'] = ('GET',),
    filter_fn: Callable = None,
    old_data_on_error: bool = False,
    session_factory=CachedSession,
    **kwargs
):
    """
    Installs cache for all ``Requests`` requests by monkey-patching ``Session``

    Parameters are the same as in :class:`CachedSession`. Additional parameters:

    Args:
        session_factory: Session class to use. It must inherit from either :py:class:`CachedSession`
            or :py:class:`CacheMixin`
    """
    if backend:
        backend = backends.create_backend(backend, cache_name, kwargs)

    class _ConfiguredCachedSession(session_factory):
        def __init__(self):
            super().__init__(
                cache_name=cache_name,
                backend=backend,
                expire_after=expire_after,
                allowable_codes=allowable_codes,
                allowable_methods=allowable_methods,
                filter_fn=filter_fn,
                old_data_on_error=old_data_on_error,
                **kwargs
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
    return requests.Session().cache if is_installed() else None


def is_installed():
    """Indicate whether or not requests-cache is installed"""
    return isinstance(requests.Session(), CachedSession)


def clear():
    """Clears globally installed cache"""
    if get_cache():
        get_cache().clear()


def remove_expired_responses():
    """Removes expired responses from storage"""
    if is_installed():
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
