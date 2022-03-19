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
from typing import TYPE_CHECKING, Callable, MutableMapping, Optional

from requests import PreparedRequest
from requests import Session as OriginalSession
from requests.hooks import dispatch_hook
from urllib3 import filepost

from ._utils import get_valid_kwargs
from .backends import BackendSpecifier, init_backend
from .cache_control import CacheActions, append_directive
from .expiration import ExpirationTime, get_expiration_seconds
from .models import (
    AnyResponse,
    CachedResponse,
    CacheSettings,
    RequestSettings,
    set_response_defaults,
)

__all__ = ['ALL_METHODS', 'CachedSession', 'CacheMixin']
ALL_METHODS = ['GET', 'HEAD', 'OPTIONS', 'POST', 'PUT', 'PATCH', 'DELETE']
FILTER_FN = Callable[[AnyResponse], bool]

logger = getLogger(__name__)
if TYPE_CHECKING:
    MIXIN_BASE = OriginalSession
else:
    MIXIN_BASE = object


# TODO: Better docs for __init__
# TODO: Better function signatures (due to passing around **kwargs instead of explicit keyword args)


class CacheMixin(MIXIN_BASE):
    """Mixin class that extends :py:class:`requests.Session` with caching features.
    See :py:class:`.CachedSession` for usage details.
    """

    def __init__(
        self,
        cache_name: str = 'http_cache',
        backend: BackendSpecifier = None,
        **kwargs,
    ):
        self.cache = init_backend(cache_name, backend, **kwargs)
        self._lock = RLock()

        # If the mixin superclass is custom Session, pass along any valid kwargs
        super().__init__(**get_valid_kwargs(super().__init__, kwargs))  # type: ignore

    def request(  # type: ignore
        self,
        method: str,
        url: str,
        *args,
        headers: MutableMapping[str, str] = None,
        expire_after: ExpirationTime = None,
        only_if_cached: bool = False,
        refresh: bool = False,
        revalidate: bool = False,
        **kwargs,
    ) -> AnyResponse:
        """This method prepares and sends a request while automatically performing any necessary
        caching operations. This will be called by any other method-specific ``requests`` functions
        (get, post, etc.). This is not used by :py:class:`~requests.PreparedRequest` objects, which
        are handled by :py:meth:`send()`.

        See :py:meth:`requests.Session.request` for parameters. Additional parameters:

        Args:
            expire_after: Expiration time to set only for this request; see details below.
                Overrides ``CachedSession.expire_after``. Accepts all the same values as
                ``CachedSession.expire_after``. Use ``-1`` to disable expiration.
            only_if_cached: Only return results from the cache. If not cached, return a 504 response
                instead of sending a new request.
            refresh: Always make a new request, and overwrite any previously cached response
            revalidate: Revalidate with the server before using a cached response (e.g., a "soft refresh")

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
        # Set extra options as headers to be handled in send(), since we can't pass args directly
        headers = headers or {}
        if expire_after is not None:
            headers = append_directive(headers, f'max-age={get_expiration_seconds(expire_after)}')
        if only_if_cached:
            headers = append_directive(headers, 'only-if-cached')
        if revalidate:
            headers = append_directive(headers, 'no-cache')
        if refresh:
            headers['requests-cache-refresh'] = 'true'
        kwargs['headers'] = headers

        with patch_form_boundary(**kwargs):
            return super().request(method, url, *args, **kwargs)

    def send(self, request: PreparedRequest, **kwargs) -> AnyResponse:
        """Send a prepared request, with caching. See :py:meth:`.request` for notes on behavior, and
        see :py:meth:`requests.Session.send` for parameters.
        """
        # Determine which actions to take based on settings and request info
        actions = CacheActions.from_request(
            self.cache.create_key(request, **kwargs),
            request,
            RequestSettings(self.settings, **kwargs),
            **kwargs,
        )

        # Attempt to fetch a cached response
        cached_response: Optional[CachedResponse] = None
        if not actions.skip_read:
            cached_response = self.cache.get_response(actions.cache_key)
        actions.update_from_cached_response(cached_response)

        # Handle missing and expired responses based on settings and headers
        if actions.error_504:
            response: AnyResponse = get_504_response(request)
        elif actions.send_request:
            response = self._send_and_cache(request, actions, cached_response, **kwargs)
        elif actions.resend_request:
            response = self._resend(request, actions, cached_response, **kwargs)  # type: ignore
        else:
            response = cached_response  # type: ignore  # Guaranteed to be non-None by this point

        # If the request has been filtered out and was previously cached, delete it
        if self.settings.filter_fn is not None and not self.settings.filter_fn(response):
            logger.debug(f'Deleting filtered response for URL: {response.url}')
            self.cache.delete(actions.cache_key)
            return response

        # Dispatch any hooks here, because they are removed during serialization
        return dispatch_hook('response', request.hooks, response, **kwargs)

    def _send_and_cache(
        self,
        request: PreparedRequest,
        actions: CacheActions,
        cached_response: CachedResponse = None,
        **kwargs,
    ) -> AnyResponse:
        """Send a request and cache the response, unless disabled by settings or headers.
        If applicable, also handle conditional requests.
        """
        request = actions.update_request(request)
        response = super().send(request, **kwargs)
        actions.update_from_response(response)

        if not actions.skip_write:
            self.cache.save_response(response, actions.cache_key, actions.expires)
        elif cached_response is not None and response.status_code == 304:
            cached_response = actions.update_revalidated_response(response, cached_response)
            self.cache.save_response(cached_response, actions.cache_key, actions.expires)
            return cached_response
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
        """Handle a stale cached response by attempting to resend the request and cache a fresh
        response
        """
        logger.debug('Stale response; attempting to re-send request')
        try:
            response = self._send_and_cache(request, actions, cached_response, **kwargs)
            if self.settings.stale_if_error:
                response.raise_for_status()
            return response
        except Exception:
            return self._handle_error(cached_response, actions)

    def _handle_error(self, cached_response: CachedResponse, actions: CacheActions) -> AnyResponse:
        """Handle a request error based on settings:
        * Default behavior: delete the stale cache item and re-raise the error
        * stale-if-error: Ignore the error and and return the stale cache item
        """
        if self.settings.stale_if_error:
            logger.warning(
                f'Request for URL {cached_response.request.url} failed; using cached response',
                exc_info=True,
            )
            return cached_response
        else:
            self.cache.delete(actions.cache_key)
            raise

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
        if self.settings.disabled:
            yield
        else:
            self.settings.disabled = True
            try:
                yield
            finally:
                self.settings.disabled = False

    @property
    def settings(self) -> CacheSettings:
        return self.cache.settings

    @settings.setter
    def settings(self, value: CacheSettings):
        self.cache.settings = value

    def remove_expired_responses(self, expire_after: ExpirationTime = None):
        """Remove expired responses from the cache, optionally with revalidation

        Args:
            expire_after: A new expiration time used to revalidate the cache
        """
        self.cache.remove_expired_responses(expire_after)

    def __repr__(self):
        return f'<CachedSession(cache={repr(self.cache)}, settings={self.settings})>'


class CachedSession(CacheMixin, OriginalSession):
    """Session class that extends :py:class:`requests.Session` with caching features.

    See individual :py:mod:`backend classes <requests_cache.backends>` for additional
    backend-specific arguments. Also see :ref:`user-guide` for more details and examples on how the
    following arguments affect cache behavior.

    Args:
        cache_name: Cache prefix or namespace, depending on backend
        backend: Cache backend name or instance; name may be one of
            ``['sqlite', 'filesystem', 'mongodb', 'gridfs', 'redis', 'dynamodb', 'memory']``
        serializer: Serializer name or instance; name may be one of
            ``['pickle', 'json', 'yaml', 'bson']``.
        kwargs: Additional keyword arguments for :py:class:`.CacheSettings` or the selected backend
    """


def get_504_response(request: PreparedRequest) -> CachedResponse:
    """Get a 504: Not Cached error response, for use with only-if-cached option"""
    return CachedResponse(
        url=request.url or '',
        status_code=504,
        reason='Not Cached',
        request=request,  # type: ignore
    )


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
