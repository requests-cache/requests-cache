"""Main classes to add caching features to ``requests.Session``

.. autosummary::
   :nosignatures:

   CachedSession
   CacheMixin

.. Explicitly show inherited method docs on CachedSession instead of CachedMixin
.. autoclass:: requests_cache.session.CachedSession
    :show-inheritance:
    :inherited-members:

.. autoclass:: requests_cache.session.CacheMixin
"""
from contextlib import contextmanager
from logging import getLogger
from threading import RLock
from typing import TYPE_CHECKING, Callable, Dict, Iterable, Optional

from requests import PreparedRequest, Response
from requests import Session as OriginalSession
from requests.hooks import dispatch_hook
from urllib3 import filepost

from ._utils import get_valid_kwargs
from .backends import BackendSpecifier, init_backend
from .cache_control import CacheActions, ExpirationTime, get_expiration_seconds
from .models import AnyResponse, CachedResponse, set_response_defaults

__all__ = ['ALL_METHODS', 'CachedSession', 'CacheMixin']
ALL_METHODS = ['GET', 'HEAD', 'OPTIONS', 'POST', 'PUT', 'PATCH', 'DELETE']
FILTER_FN = Callable[[AnyResponse], bool]

logger = getLogger(__name__)
if TYPE_CHECKING:
    MIXIN_BASE = OriginalSession
else:
    MIXIN_BASE = object


class CacheMixin(MIXIN_BASE):
    """Mixin class that extends :py:class:`requests.Session` with caching features.
    See :py:class:`.CachedSession` for usage details.
    """

    def __init__(
        self,
        cache_name: str = 'http_cache',
        backend: BackendSpecifier = None,
        expire_after: ExpirationTime = -1,
        urls_expire_after: Dict[str, ExpirationTime] = None,
        cache_control: bool = False,
        allowable_codes: Iterable[int] = (200,),
        allowable_methods: Iterable[str] = ('GET', 'HEAD'),
        filter_fn: FILTER_FN = None,
        stale_if_error: bool = False,
        **kwargs,
    ):
        self.cache = init_backend(cache_name, backend, **kwargs)
        self.allowable_codes = allowable_codes
        self.allowable_methods = allowable_methods
        self.expire_after = expire_after
        self.urls_expire_after = urls_expire_after
        self.cache_control = cache_control
        self.filter_fn = filter_fn or (lambda r: True)
        self.stale_if_error = stale_if_error or kwargs.pop('old_data_on_error', False)

        self._disabled = False
        self._lock = RLock()

        # If the superclass is custom Session, pass along any valid kwargs
        session_kwargs = get_valid_kwargs(super().__init__, kwargs)
        super().__init__(**session_kwargs)  # type: ignore

    def request(  # type: ignore  # Note: An extra param (expire_after) is added here
        self,
        method: str,
        url: str,
        *args,
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
                ``CachedSession.expire_after``. Use ``-1`` to disable expiration.

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
        # If present, set per-request expiration as a request header, to be handled in send()
        if expire_after is not None:
            kwargs.setdefault('headers', {})
            kwargs['headers']['Cache-Control'] = f'max-age={get_expiration_seconds(expire_after)}'

        with patch_form_boundary(**kwargs):
            return super().request(method, url, *args, **kwargs)

    def send(
        self, request: PreparedRequest, expire_after: ExpirationTime = None, **kwargs
    ) -> AnyResponse:
        """Send a prepared request, with caching. See :py:meth:`.request` for notes on behavior, and
        see :py:meth:`requests.Session.send` for parameters. Additional parameters:

        Args:
            expire_after: Expiration time to set only for this request
        """
        # Determine which actions to take based on request info and cache settings
        cache_key = self.cache.create_key(request, **kwargs)
        actions = CacheActions.from_request(
            cache_key=cache_key,
            request=request,
            request_expire_after=expire_after,
            session_expire_after=self.expire_after,
            urls_expire_after=self.urls_expire_after,
            cache_control=self.cache_control,
            **kwargs,
        )

        # Attempt to fetch a cached response
        cached_response: Optional[CachedResponse] = None
        if not (self._disabled or actions.skip_read):
            cached_response = self.cache.get_response(cache_key)
            actions.update_from_cached_response(cached_response)
        is_expired = getattr(cached_response, 'is_expired', False)

        # If the response is expired or missing, or the cache is disabled, then fetch a new response
        if cached_response is None:
            response = self._send_and_cache(request, actions, **kwargs)
        elif is_expired and self.stale_if_error:
            response = self._resend_and_ignore(request, actions, cached_response, **kwargs)
        elif is_expired:
            response = self._resend(request, actions, cached_response, **kwargs)
        else:
            response = cached_response

        # If the request has been filtered out and was previously cached, delete it
        if not self.filter_fn(response):
            logger.debug(f'Deleting filtered response for URL: {response.url}')
            self.cache.delete(cache_key)
            return response

        # Dispatch any hooks here, because they are removed before pickling
        return dispatch_hook('response', request.hooks, response, **kwargs)

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

    def _send_and_cache(
        self,
        request: PreparedRequest,
        actions: CacheActions,
        cached_response: CachedResponse = None,
        **kwargs,
    ) -> AnyResponse:
        """Send the request and cache the response, unless disabled by settings or headers.

        If applicable, also add headers to make a conditional request. If we get a 304 Not Modified
        response, return the stale cache item.
        """
        request.headers.update(actions.validation_headers)
        response = super().send(request, **kwargs)
        actions.update_from_response(response)

        if self._is_cacheable(response, actions):
            self.cache.save_response(response, actions.cache_key, actions.expires)
        elif cached_response and response.status_code == 304:
            return self._update_revalidated_response(actions, response, cached_response)
        else:
            logger.debug(f'Skipping cache write for URL: {request.url}')
        return set_response_defaults(response, actions.cache_key)

    def _resend(
        self,
        request: PreparedRequest,
        actions: CacheActions,
        cached_response: CachedResponse,
        **kwargs,
    ) -> AnyResponse:
        """Attempt to resend the request and cache the new response. If the request fails, delete
        the stale cache item.
        """
        logger.debug('Stale response; attempting to re-send request')
        try:
            return self._send_and_cache(request, actions, cached_response, **kwargs)
        except Exception:
            self.cache.delete(actions.cache_key)
            raise

    def _resend_and_ignore(
        self,
        request: PreparedRequest,
        actions: CacheActions,
        cached_response: CachedResponse,
        **kwargs,
    ) -> AnyResponse:
        """Attempt to resend the request and cache the new response. If there are any errors, ignore
        them and and return the stale cache item.
        """
        # Attempt to send the request and cache the new response
        logger.debug('Stale response; attempting to re-send request')
        try:
            response = self._send_and_cache(request, actions, cached_response, **kwargs)
            response.raise_for_status()
            return response
        except Exception:
            logger.warning(
                f'Request for URL {request.url} failed; using cached response', exc_info=True
            )
            return cached_response

    def _update_revalidated_response(
        self, actions: CacheActions, response: Response, cached_response: CachedResponse
    ) -> CachedResponse:
        """After revalidation, update the cached response's headers and reset its expiration"""
        logger.debug(
            f'Response for URL {response.request.url} has not been modified; updating and using cached response'
        )
        cached_response.headers.update(response.headers)
        actions.update_from_response(cached_response)
        cached_response.expires = actions.expires
        self.cache.save_response(cached_response, actions.cache_key, actions.expires)
        return cached_response

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
            'stale_if_error',
            'cache_control',
        ]
        attr_strs = [f'{k}={repr(getattr(self, k))}' for k in repr_attrs]
        return f'<CachedSession({", ".join(attr_strs)})>'


class CachedSession(CacheMixin, OriginalSession):
    """Session class that extends :py:class:`requests.Session` with caching features.

    See individual :py:mod:`backend classes <requests_cache.backends>` for additional backend-specific arguments.
    Also see :ref:`user-guide` for more details and examples on how the following arguments
    affect cache behavior.

    Args:
        cache_name: Cache prefix or namespace, depending on backend
        backend: Cache backend name or instance; name may be one of
            ``['sqlite', 'filesystem', 'mongodb', 'gridfs', 'redis', 'dynamodb', 'memory']``
        serializer: Serializer name or instance; name may be one of
            ``['pickle', 'json', 'yaml', 'bson']``.
        expire_after: Time after which cached items will expire
        urls_expire_after: Expiration times to apply for different URL patterns
        cache_control: Use Cache-Control headers to set expiration
        allowable_codes: Only cache responses with one of these status codes
        allowable_methods: Cache only responses for one of these HTTP methods
        match_headers: Match request headers when reading from the cache; may be either a boolean
            or a list of specific headers to match
        ignored_parameters: List of request parameters to not match against, and exclude from the cache
        filter_fn: Function that takes a :py:class:`~requests.Response` object and returns a boolean
            indicating whether or not that response should be cached. Will be applied to both new
            and previously cached responses.
        key_fn: Function for generating custom cache keys based on request info
        stale_if_error: Return stale cache data if a new request raises an exception
    """


@contextmanager
def patch_form_boundary(**request_kwargs):
    """If the ``files`` param is present, patch the form boundary used to separate multipart
    uploads. ``requests`` does not provide a way to pass a custom boundary to urllib3, so this just
    monkey-patches it instead.
    """
    if request_kwargs.get('files'):
        original_boundary = filepost.choose_boundary
        filepost.choose_boundary = lambda: '##requests-cache-form-boundary##'
        yield
        filepost.choose_boundary = original_boundary
    else:
        yield
