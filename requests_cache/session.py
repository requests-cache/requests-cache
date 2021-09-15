"""Main classes to add caching features to ``requests.Session``"""
from contextlib import contextmanager
from logging import getLogger
from threading import RLock
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, Optional

from requests import PreparedRequest, Response
from requests import Session as OriginalSession
from requests.hooks import dispatch_hook
from urllib3 import filepost

from .backends import BackendSpecifier, get_valid_kwargs, init_backend
from .cache_control import CacheActions, ExpirationTime
from .cache_keys import normalize_dict
from .models import AnyResponse, set_response_defaults

ALL_METHODS = ['GET', 'HEAD', 'OPTIONS', 'POST', 'PUT', 'PATCH', 'DELETE']

logger = getLogger(__name__)
# MIXIN_BASE: Type = OriginalSession if TYPE_CHECKING else object
if TYPE_CHECKING:
    MIXIN_BASE = OriginalSession
else:
    MIXIN_BASE = object


class CacheMixin(MIXIN_BASE):
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
        allowable_methods: Iterable[str] = ('GET', 'HEAD'),
        filter_fn: Callable = None,
        old_data_on_error: bool = False,
        cache_control: bool = False,
        **kwargs,
    ):
        self.cache = init_backend(backend, cache_name, **kwargs)
        self.allowable_codes = allowable_codes
        self.allowable_methods = allowable_methods
        self.expire_after = expire_after
        self.urls_expire_after = urls_expire_after
        self.filter_fn = filter_fn or (lambda r: True)
        self.old_data_on_error = old_data_on_error or kwargs.get('stale_if_error', False)
        self.cache_control = cache_control

        self.cache.name = cache_name  # Set to handle backend=<instance>
        self._request_expire_after: ExpirationTime = None
        self._disabled = False
        self._lock = RLock()

        # If the superclass is custom Session, pass along valid kwargs (if any)
        session_kwargs = get_valid_kwargs(super().__init__, kwargs)
        super().__init__(**session_kwargs)  # type: ignore

    def request(  # type: ignore  # Note: Session.request() doesn't have expire_after param
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

        **Order of operations:** For reference, a request will pass through the following methods:

        1. :py:func:`requests.get`/:py:meth:`requests.Session.get` or other method-specific functions (optional)
        2. :py:meth:`.CachedSession.request`
        3. :py:meth:`requests.Session.request`
        4. :py:meth:`.CachedSession.send`
        5. :py:meth:`.BaseCache.get_response`
        6. :py:meth:`requests.Session.send` (if not previously cached)
        7. :py:meth:`.BaseCache.save_response` (if not previously cached)

        """
        with self.request_expire_after(expire_after), patch_form_boundary(**kwargs):
            return super().request(
                method,
                url,
                params=normalize_dict(params),
                data=normalize_dict(data),
                json=normalize_dict(json),
                **kwargs,
            )

    def send(self, request: PreparedRequest, **kwargs) -> AnyResponse:
        """Send a prepared request, with caching. See :py:meth:`.request` for notes on behavior."""
        # Determine which actions to take based on request info, headers, and cache settings
        cache_key = self.cache.create_key(request, **kwargs)
        actions = CacheActions(
            cache_key=cache_key,
            request=request,
            request_expire_after=self._request_expire_after,
            session_expire_after=self.expire_after,
            urls_expire_after=self.urls_expire_after,
            cache_control=self.cache_control,
            **kwargs,
        )

        # Attempt to fetch a cached response
        response: Optional[AnyResponse] = None
        if not (self._disabled or actions.skip_read):
            response = self.cache.get_response(cache_key)
        is_expired = getattr(response, 'is_expired', False)

        # If the cache is disabled, doesn't have the response, or it's expired, then fetch a new one
        if response is None:
            response = self._send_and_cache(request, actions, **kwargs)
        elif is_expired and self.old_data_on_error:
            response = self._resend_and_ignore(request, actions, **kwargs) or response
        elif is_expired:
            response = self._resend(request, actions, **kwargs)

        # Dispatch any hooks here, because they are removed before pickling
        response = dispatch_hook('response', request.hooks, response, **kwargs)
        if TYPE_CHECKING:
            assert response is not None

        # If the request has been filtered out, delete previously cached response if it exists
        if not self.filter_fn(response):
            logger.debug(f'Deleting filtered response for URL: {response.url}')
            self.cache.delete(cache_key)
            return response

        # Cache redirect history
        for r in response.history:
            self.cache.save_redirect(r.request, cache_key)
        return response

    def _send_and_cache(self, request: PreparedRequest, actions: CacheActions, **kwargs):
        """Send the request and cache the response, unless disabled by settings or headers"""
        response = super().send(request, **kwargs)
        actions.update_from_response(response)

        if self._is_cacheable(response, actions):
            self.cache.save_response(response, actions.cache_key, actions.expires)
        else:
            logger.debug(f'Skipping cache write for URL: {request.url}')
        return set_response_defaults(response, actions.cache_key)

    def _resend(self, request: PreparedRequest, actions: CacheActions, **kwargs) -> AnyResponse:
        """Attempt to resend the request and cache the new response. If the request fails, delete
        the expired cache item.
        """
        logger.debug('Expired response; attempting to re-send request')
        try:
            return self._send_and_cache(request, actions, **kwargs)
        except Exception:
            self.cache.delete(actions.cache_key)
            raise

    def _resend_and_ignore(
        self, request: PreparedRequest, actions: CacheActions, **kwargs
    ) -> Optional[AnyResponse]:
        """Attempt to send the request and cache the new response. If there are any errors, ignore
        them and and return ``None``.
        """
        # Attempt to send the request and cache the new response
        logger.debug('Expired response; attempting to re-send request')
        try:
            response = self._send_and_cache(request, actions, **kwargs)
            response.raise_for_status()
            return response
        except Exception as e:
            logger.warning('Request failed; using stale cache data: %s', e)
            return None

    def _is_cacheable(self, response: Response, actions: CacheActions) -> bool:
        """Perform all checks needed to determine if the given response should be saved to the cache"""
        cache_criteria = {
            'disabled cache': self._disabled,
            'disabled method': str(response.request.method) not in self.allowable_methods,
            'disabled status': response.status_code not in self.allowable_codes,
            'disabled by filter': not self.filter_fn(response),
            'disabled by headers or expiration params': actions.skip_write,
        }
        logger.debug(f'Pre-cache checks for response from {response.url}: {cache_criteria}')
        return not any(cache_criteria.values())

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
        repr_attrs = [
            'cache',
            'expire_after',
            'urls_expire_after',
            'allowable_codes',
            'allowable_methods',
            'old_data_on_error',
            'cache_control',
        ]
        attr_strs = [f'{k}={repr(getattr(self, k))}' for k in repr_attrs]
        return f'<CachedSession({", ".join(attr_strs)})>'


class CachedSession(CacheMixin, OriginalSession):
    """Class that extends :py:class:`requests.Session` with caching features.

    See individual :py:mod:`backend classes <requests_cache.backends>` for additional backend-specific arguments.
    Also see :ref:`user-guide` for more details and examples on how the following arguments
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
        old_data_on_error: Return stale cache data if a new request raises an exception
        cache_control: Use Cache-Control request and response headers
    """


@contextmanager
def patch_form_boundary(**request_kwargs):
    """This patches the form boundary used to separate multipart uploads. Requests does not
    provide a way to pass a custom boundary to urllib3, so this just monkey-patches it instead.
    """
    if request_kwargs.get('files'):
        original_boundary = filepost.choose_boundary
        filepost.choose_boundary = lambda: '##requests-cache-form-boundary##'
        yield
        filepost.choose_boundary = original_boundary
    else:
        yield
