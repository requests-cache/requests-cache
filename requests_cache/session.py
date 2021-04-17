"""Main classes to add caching features to ``requests.Session``"""
from contextlib import contextmanager
from fnmatch import fnmatch
from logging import getLogger
from threading import RLock
from typing import Any, Callable, Dict, Iterable

from requests import PreparedRequest
from requests import Session as OriginalSession
from requests.hooks import dispatch_hook

from .backends import BACKEND_KWARGS, BackendSpecifier, init_backend
from .cache_keys import normalize_dict
from .response import AnyResponse, ExpirationTime, set_response_defaults

ALL_METHODS = ['GET', 'HEAD', 'OPTIONS', 'POST', 'PUT', 'PATCH', 'DELETE']
logger = getLogger(__name__)


class CacheMixin:
    """Mixin class that extends :py:class:`requests.Session` with caching features.
    See :py:class:`.CachedSession` for usage information.
    """

    def __init__(
        self,
        cache_name: str = 'http_cache',
        backend: BackendSpecifier = None,
        expire_after: ExpirationTime = -1,
        urls_expire_after: Dict[str, ExpirationTime] = None,
        allowable_codes: Iterable[int] = (200,),
        allowable_methods: Iterable['str'] = ('GET', 'HEAD'),
        filter_fn: Callable = None,
        old_data_on_error: bool = False,
        **kwargs,
    ):
        self.cache = init_backend(backend, cache_name, **kwargs)
        self.allowable_codes = allowable_codes
        self.allowable_methods = allowable_methods
        self.expire_after = expire_after
        self.urls_expire_after = urls_expire_after
        self.filter_fn = filter_fn or (lambda r: True)
        self.old_data_on_error = old_data_on_error

        self._cache_name = cache_name
        self._request_expire_after: ExpirationTime = None
        self._disabled = False
        self._lock = RLock()

        # Remove any requests-cache-specific kwargs before passing along to superclass
        session_kwargs = {k: v for k, v in kwargs.items() if k not in BACKEND_KWARGS}
        super().__init__(**session_kwargs)

    def request(
        self,
        method: str,
        url: str,
        params: Dict = None,
        data: Any = None,
        json: Dict = None,
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
                params=normalize_dict(params),
                data=normalize_dict(data),
                json=normalize_dict(json),
                **kwargs,
            )
        if self._disabled:
            return response

        # If the request has been filtered out, delete previously cached response if it exists
        cache_key = self.cache.create_key(response.request, **kwargs)
        if not response.from_cache and not self.filter_fn(response):
            logger.debug(f'Deleting filtered response for URL: {response.url}')
            self.cache.delete(cache_key)
            return response

        # Cache redirect history
        for r in response.history:
            self.cache.save_redirect(r.request, cache_key)
        return response

    def send(self, request: PreparedRequest, **kwargs) -> AnyResponse:
        """Send a prepared request, with caching."""
        # If we shouldn't cache the response, just send the request
        if not self._is_cacheable(request):
            logger.debug(f'Request for URL {request.url} is not cacheable')
            response = super().send(request, **kwargs)
            return set_response_defaults(response)

        # Attempt to fetch the cached response
        cache_key = self.cache.create_key(request, **kwargs)
        response = self.cache.get_response(cache_key)

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
        logger.debug('Expired response; attempting to re-send request')
        try:
            return self._send_and_cache(request, cache_key, **kwargs)
        # Return the expired/invalid response on error, if specified; otherwise reraise
        except Exception as e:
            logger.exception(e)
            if self.old_data_on_error:
                logger.warning('Request failed; using stale cache data')
                return response
            self.cache.delete(cache_key)
            raise

    def _send_and_cache(self, request, cache_key, **kwargs):
        logger.debug(f'Sending request and caching response for URL: {request.url}')
        response = super().send(request, **kwargs)
        if response.status_code in self.allowable_codes:
            self.cache.save_response(cache_key, response, self._get_expiration(request.url))
        return set_response_defaults(response)

    @contextmanager
    def cache_disabled(self):
        """
        Context manager for temporary disabling the cache

        .. warning:: This method is not thread-safe.

        Example:

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

    def _get_expiration(self, url: str = None) -> ExpirationTime:
        """Get the appropriate expiration, in order of precedence:
        1. Per-request expiration
        2. Per-URL expiration
        3. Per-session expiration
        """
        return self._request_expire_after or self._url_expire_after(url) or self.expire_after

    def _url_expire_after(self, url: str) -> ExpirationTime:
        """Get the expiration time for a URL, if a matching pattern is defined"""
        for pattern, expire_after in (self.urls_expire_after or {}).items():
            if url_match(url, pattern):
                return expire_after
        return None

    @contextmanager
    def request_expire_after(self, expire_after: ExpirationTime = None):
        """Temporarily override ``expire_after`` for an individual request. This is needed to
        persist the value between requests.Session.request() -> send()."""
        # TODO: Is there a way to pass this via request kwargs -> PreparedRequest?
        with self._lock:
            self._request_expire_after = expire_after
            yield
            self._request_expire_after = None

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


class CachedSession(CacheMixin, OriginalSession):
    """Class that extends :py:class:`requests.Session` with caching features.

    See individual :py:mod:`backend classes <requests_cache.backends>` for additional backend-specific arguments.
    Also see :ref:`advanced_usage` for more details and examples on how the following arguments
    affect cache behavior.

    Args:
        cache_name: Cache prefix or namespace, depending on backend
        backend: Cache backend name, class, or instance; name may be one of
            ``['sqlite', 'mongodb', 'gridfs', 'redis', 'dynamodb', 'memory']``.
        expire_after: Time after which cached items will expire
        urls_expire_after: Expiration times to apply for different URL patterns
        allowable_codes: Only cache responses with one of these codes
        allowable_methods: Cache only responses for one of these HTTP methods
        include_get_headers: Make request headers part of the cache key
        ignored_parameters: List of request parameters to be excluded from the cache key
        filter_fn: function that takes a :py:class:`aiohttp.ClientResponse` object and
            returns a boolean indicating whether or not that response should be cached. Will be
            applied to both new and previously cached responses.
        old_data_on_error: Return expired cached responses if new request fails
        secret_key: Optional secret key used to sign cache items for added security

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
