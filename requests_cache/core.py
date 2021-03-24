"""
    requests_cache.core
    ~~~~~~~~~~~~~~~~~~~

    Core functions for configuring cache and monkey patching ``requests``
"""
from collections.abc import Mapping
from contextlib import contextmanager
from fnmatch import fnmatch
from operator import itemgetter
from typing import Any, Callable, Dict, Iterable, Optional, Type

import requests
from requests import PreparedRequest
from requests import Session as OriginalSession
from requests.hooks import dispatch_hook

from . import backends
from .response import AnyResponse, ExpirationTime, set_response_defaults

ALL_METHODS = ['GET', 'HEAD', 'OPTIONS', 'POST', 'PUT', 'PATCH', 'DELETE']


class CacheMixin:
    """Mixin class that extends :py:class:`requests.Session` with caching features.
    See :py:class:`.CachedSession` for usage information.
    """

    def __init__(
        self,
        cache_name: str = 'cache',
        backend: str = None,
        expire_after: ExpirationTime = -1,
        urls_expire_after: Dict[str, ExpirationTime] = None,
        allowable_codes: Iterable[int] = (200,),
        allowable_methods: Iterable['str'] = ('GET', 'HEAD'),
        filter_fn: Callable = None,
        old_data_on_error: bool = False,
        **kwargs,
    ):
        self.cache = backends.create_backend(backend, cache_name, kwargs)
        self.allowable_codes = allowable_codes
        self.allowable_methods = allowable_methods
        self.expire_after = expire_after
        self.urls_expire_after = urls_expire_after
        self.filter_fn = filter_fn or (lambda r: True)
        self.old_data_on_error = old_data_on_error

        self._cache_name = cache_name
        self._request_expire_after: ExpirationTime = None
        self._disabled = False

        # Remove any requests-cache-specific kwargs before passing along to superclass
        session_kwargs = {k: v for k, v in kwargs.items() if k not in backends.BACKEND_KWARGS}
        super().__init__(**session_kwargs)

    def request(
        self,
        method: str,
        url: str,
        params: Dict = None,
        data: Any = None,
        expire_after: ExpirationTime = None,
        **kwargs,
    ) -> AnyResponse:
        """This method prepares and sends a request while automatically performing any necessary
        caching operations. This will be called by any other method-specific ``requests`` functions
        (get, post, etc.). This does not include prepared requests, which will still be cached via
        ``send()``.

        See :py:meth:`requests.Session.request` for parameters. Additional parameters:

        Args:
            expire_after: Expiration time to set only for this request; see details below.
                Overrides ``CachedSession.expire_after``. Accepts all the same values as
                ``CachedSession.expire_after`` except for ``None``; use ``-1`` to disable expiration
                on a per-request basis.

        Returns:
            Either a new or cached response

        **Order of operations:** A request will pass through the following methods:

        1. :py:func:`requests.get`/:py:meth:`requests.Session.get` or other method-specific functions (optional)
        2. :py:meth:`.CachedSession.request`
        3. :py:meth:`requests.Session.request`
        4. :py:meth:`.CachedSession.send`
        5. :py:meth:`.BaseCache.get_response`
        6. :py:meth:`requests.Session.send` (if not cached)
        """
        with self.request_expire_after(expire_after):
            response = super().request(
                method,
                url,
                _normalize_parameters(params),
                _normalize_parameters(data),
                **kwargs,
            )
        if self._disabled:
            return response

        # If the request has been filtered out, delete previously cached response if it exists
        main_key = self.cache.create_key(response.request)
        if not response.from_cache and not self.filter_fn(response):
            self.cache.delete(main_key)
            return response

        # Cache redirect history
        for r in response.history:
            self.cache.add_key_mapping(self.cache.create_key(r.request), main_key)
        return response

    def send(self, request: PreparedRequest, **kwargs) -> AnyResponse:
        """Send a prepared request, with caching."""
        # If we shouldn't cache the response, just send the request
        if not self._is_cacheable(request):
            response = super().send(request, **kwargs)
            return set_response_defaults(response)

        # Attempt to fetch the cached response
        cache_key = self.cache.create_key(request)
        try:
            response = self.cache.get_response(cache_key)
        except (ImportError, TypeError, ValueError):
            response = None

        # Attempt to fetch and cache a new response, if needed
        if response is None:
            return self._send_and_cache(request, cache_key, **kwargs)
        if response.is_expired:
            return self._handle_expired_response(request, response, cache_key, **kwargs)

        # Dispatch hook here, because we've removed it before pickling
        return dispatch_hook('response', request.hooks, response, **kwargs)

    def _is_cacheable(self, request: PreparedRequest) -> bool:
        criteria = [
            not self._disabled,
            str(request.method) in self.allowable_methods,
            self.filter_fn(request),
        ]
        return all(criteria)

    def _handle_expired_response(self, request, response, cache_key, **kwargs) -> AnyResponse:
        """Determine what to do with an expired response, depending on old_data_on_error setting"""
        # Attempt to send the request and cache the new response
        try:
            new_response = self._send_and_cache(request, cache_key, **kwargs)
            self.cache.delete(cache_key)
            return new_response
        # Return the expired/invalid response on error, if specified; otherwise reraise
        except Exception:
            if self.old_data_on_error:
                return response
            self.cache.delete(cache_key)
            raise

    def _send_and_cache(self, request, cache_key, **kwargs):
        response = super().send(request, **kwargs)
        if response.status_code in self.allowable_codes:
            self.cache.save_response(cache_key, response, self.get_expiration(request.url))
        return set_response_defaults(response)

    @contextmanager
    def cache_disabled(self):
        """
        Context manager for temporary disabling the cache
        ::

            >>> s = CachedSession()
            >>> with s.cache_disabled():
            ...     s.get('http://httpbin.org/ip')
        """
        if self._disabled:
            yield
        else:
            self._disabled = True
            try:
                yield
            finally:
                self._disabled = False

    def get_expiration(self, url: str = None) -> ExpirationTime:
        """Get the appropriate expiration, in order of precedence:
        1. Per-request expiration
        2. Per-URL expiration
        3. Per-session expiration
        """
        return self._request_expire_after or self.url_expire_after(url) or self.expire_after

    @contextmanager
    def request_expire_after(self, expire_after: ExpirationTime = None):
        """Temporarily override ``expire_after`` for an individual request"""
        self._request_expire_after = expire_after
        yield
        self._request_expire_after = None

    def url_expire_after(self, url: str) -> ExpirationTime:
        """Get the expiration time for a URL, if a matching pattern is defined"""
        for pattern, expire_after in (self.urls_expire_after or {}).items():
            if url_match(url, pattern):
                return expire_after
        return None

    def remove_expired_responses(self, expire_after: ExpirationTime = None):
        """Remove expired responses from the cache, optionally with revalidation

        Args:
            expire_after: A new expiration time used to revalidate the cache
        """
        self.cache.remove_expired_responses(expire_after)

    def __repr__(self):
        return (
            f"<CachedSession({self.cache.__class__.__name__}('{self._cache_name}', ...), "
            f"expire_after={self.expire_after}, allowable_methods={self.allowable_methods})>"
        )


# TODO: Move details/examples to user guide
class CachedSession(CacheMixin, OriginalSession):
    """Class that extends ``requests.Session`` with caching features.
    See individual backend classes for additional backend-specific arguments.

    Args:
        cache_name: Cache prefix or namespace, depending on backend
        backend: Cache backend name; one of ``['sqlite', 'mongodb', 'gridfs', 'redis', 'dynamodb', 'memory']``.
                Default behavior is to use ``'sqlite'`` if available, otherwise fallback to ``'memory'``.
        expire_after: Time after which cached items will expire (see notes below)
        expire_after_urls: Expiration times to apply for different URL patterns (see notes below)
        allowable_codes: Only cache responses with one of these codes
        allowable_methods: Cache only responses for one of these HTTP methods
        include_get_headers: Make request headers part of the cache key
        ignored_parameters: List of request parameters to be excluded from the cache key
        filter_fn: function that takes a :py:class:`aiohttp.ClientResponse` object and
            returns a boolean indicating whether or not that response should be cached. Will be
            applied to both new and previously cached responses.
        old_data_on_error: Return expired cached responses if new request fails
        secret_key: Optional secret key used to sign cache items for added security

    **Cache Name:**

    The ``cache_name`` parameter will be used as follows depending on the backend:

    * ``sqlite``: Cache filename, e.g ``my_cache.sqlite``
    * ``mongodb``: Database name
    * ``redis``: Namespace, meaning all keys will be prefixed with ``'cache_name:'``

    **Cache Keys:**

    The cache key is a hash created from request information, and is used as an index for cached
    responses. There are a couple ways you can customize how the cache key is created:

    * Use ``include_get_headers`` if you want headers to be included in the cache key. In other
      words, this will create separate cache items for responses with different headers.
    * Use ``ignored_parameters`` to exclude specific request params from the cache key. This is
      useful, for example, if you request the same resource with different credentials or access
      tokens.

    **Cache Expiration:**

    Use ``expire_after`` to specify how long responses will be cached. This can be a number
    (in seconds), a :py:class:`.timedelta`, or a :py:class:`datetime`. Use ``-1`` to never expire.
    This will not apply to responses cached in the current session; to apply a different expiration
    to previously cached responses, see :py:meth:`remove_expired_responses`.

    Expiration can also be set on a per-URL or per request basis. The following order of precedence
    is used:

    1. Per-request expiration (``expire_after`` argument for :py:meth:`.request`)
    2. Per-URL expiration (``urls_expire_after`` argument for ``CachedSession``)
    3. Per-session expiration (``expire_after`` argument for ``CachedSession``)

    **URL Patterns:**

    The ``expire_after_urls`` parameter can be used to set different expiration times for different
    requests, based on URL glob patterns. This allows you to customize caching based on what you
    know about the resources you're requesting. For example, you might request one resource that
    gets updated frequently, another that changes infrequently, and another that never changes.

    Example::

        urls_expire_after = {
            '*.site_1.com': 30,
            'site_2.com/resource_1': 60 * 2,
            'site_2.com/resource_2': 60 * 60 * 24,
            'site_2.com/static': -1,
        }

    Notes:

    * ``urls_expire_after`` should be a dict in the format ``{'pattern': expire_after}``
    * ``expire_after`` accepts the same types as ``CachedSession.expire_after``
    * Patterns will match request **base URLs**, so the pattern ``site.com/resource/`` is equivalent to
      ``http*://site.com/resource/**``
    * If there is more than one match, the first match will be used in the order they are defined
    * If no patterns match a request, ``expire_after`` will be used as a default.

    """


def url_match(url: str, pattern: str) -> bool:
    """Determine if a URL matches a pattern.

    Args:
        url: URL to test. Its base URL (without protocol) will be used.
        pattern: Glob pattern to match against. A recursive wildcard will be added if not present

    Example:
        >>> url_match('https://httpbin.org/delay/1', 'httpbin.org/delay')
        True
        >>> url_match('https://httpbin.org/stream/1', 'httpbin.org/*/1')
        True
        >>> url_match('https://httpbin.org/stream/2', 'httpbin.org/*/1')
        False
    """
    if not url:
        return False
    url = url.split('://')[-1]
    pattern = pattern.split('://')[-1].rstrip('*') + '**'
    return fnmatch(url, pattern)


def install_cache(
    cache_name: str = 'cache',
    backend: str = None,
    expire_after: ExpirationTime = None,
    urls_expire_after: Dict[str, ExpirationTime] = None,
    allowable_codes: Iterable[int] = (200,),
    allowable_methods: Iterable['str'] = ('GET', 'HEAD'),
    filter_fn: Callable = None,
    old_data_on_error: bool = False,
    session_factory: Type[OriginalSession] = CachedSession,
    **kwargs,
):
    """
    Installs cache for all ``requests`` functions by monkey-patching ``Session``

    Parameters are the same as in :py:class:`CachedSession`. Additional parameters:

    Args:
        session_factory: Session class to use. It must inherit from either :py:class:`CachedSession`
            or :py:class:`CacheMixin`
    """

    class _ConfiguredCachedSession(session_factory):
        def __init__(self):
            super().__init__(
                cache_name=cache_name,
                backend=backend,
                expire_after=expire_after,
                urls_expire_after=urls_expire_after,
                allowable_codes=allowable_codes,
                allowable_methods=allowable_methods,
                filter_fn=filter_fn,
                old_data_on_error=old_data_on_error,
                **kwargs,
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


def remove_expired_responses(expire_after: ExpirationTime = None):
    """Remove expired responses from the cache, optionally with revalidation

    Args:
        expire_after: A new expiration time used to revalidate the cache
    """
    if is_installed():
        return requests.Session().remove_expired_responses(expire_after)


def _patch_session_factory(session_factory: Type[OriginalSession] = CachedSession):
    requests.Session = requests.sessions.Session = session_factory  # noqa


def _normalize_parameters(params: Optional[Dict]) -> Dict:
    """If builtin dict is passed as parameter, returns sorted list
    of key-value pairs
    """
    if isinstance(params, Mapping):
        return dict(sorted(params.items(), key=itemgetter(0)))
    return params or {}
