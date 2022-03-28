"""Internal utilities for determining cache expiration and other cache actions. This module defines
the majority of the caching policy, and resulting actions are handled in
:py:meth:`CachedSession.send`.

.. automodsumm:: requests_cache.cache_control
   :classes-only:
   :nosignatures:

.. automodsumm:: requests_cache.cache_control
   :functions-only:
   :nosignatures:
"""
from __future__ import annotations

from datetime import datetime
from logging import getLogger
from typing import Dict, MutableMapping, Optional, Tuple, Union

from attr import define, field
from requests import PreparedRequest, Response
from requests.models import CaseInsensitiveDict

from ._utils import coalesce, try_int
from .expiration import (
    DO_NOT_CACHE,
    NEVER_EXPIRE,
    ExpirationTime,
    get_expiration_datetime,
    get_url_expiration,
)
from .models import CachedResponse, CacheSettings, RequestSettings

__all__ = ['CacheActions']

# Temporary header only used to support the 'refresh' option in CachedSession.request()
REFRESH_TEMP_HEADER = 'requests-cache-refresh'

CacheDirective = Union[None, int, bool]
logger = getLogger(__name__)


@define
class CacheActions:
    """Translates cache settings and headers into specific actions to take for a given cache item.

    * See :ref:`precedence` for behavior if multiple sources provide an expiration
    * See :ref:`headers` for more details about header behavior

    Args:
        cache_key: The cache key created based on the initial request
        error_504: Indicates the request cannot be fulfilled based on cache settings
        expire_after: User or header-provided expiration value
        send_request: Send a new request
        resend_request: Send a new request to refresh a stale cache item
        skip_read: Skip reading from the cache
        skip_write: Skip writing to the cache
        _settings: Merged session-level and request-level cache settings
        _validation_headers: Headers to send with conditional requests

    """

    # Outputs
    cache_key: str = field(default=None)
    error_504: bool = field(default=False)
    expire_after: ExpirationTime = field(default=None)
    resend_request: bool = field(default=False)
    send_request: bool = field(default=False)
    skip_read: bool = field(default=False)
    skip_write: bool = field(default=False)

    # Inputs/internal attributes
    _settings: CacheSettings = field(default=None)
    _validation_headers: Dict[str, str] = field(factory=dict)

    @classmethod
    def from_request(
        cls,
        cache_key: str,
        request: PreparedRequest,
        settings: CacheSettings,
        **kwargs,
    ):
        """Initialize from request info and cache settings"""
        request.headers = request.headers or CaseInsensitiveDict()
        directives = get_cache_directives(request.headers)
        logger.debug(f'Cache directives from request headers: {directives}')

        # Merge session settings, request settings
        settings = RequestSettings(settings, **kwargs)
        settings.only_if_cached = settings.only_if_cached or 'only-if-cached' in directives
        settings.refresh = settings.refresh or bool(request.headers.pop(REFRESH_TEMP_HEADER, False))
        settings.revalidate = settings.revalidate or 'no-cache' in directives

        # Check expiration values in order of precedence
        expire_after = coalesce(
            directives.get('max-age'),
            settings.request_expire_after,
            get_url_expiration(request.url, settings.urls_expire_after),
            settings.expire_after,
        )

        # Check conditions for reading from the cache
        skip_read = any(
            [
                settings.refresh,
                settings.disabled,
                'no-store' in directives,
                try_int(expire_after) == DO_NOT_CACHE,
            ]
        )

        return cls(
            cache_key=cache_key,
            expire_after=expire_after,
            skip_read=skip_read,
            skip_write='no-store' in directives,
            settings=settings,
        )

    @property
    def expires(self) -> Optional[datetime]:
        """Convert the user/header-provided expiration value to a datetime"""
        return get_expiration_datetime(self.expire_after)

    def update_from_cached_response(self, cached_response: CachedResponse):
        """Check for relevant cache headers from a cached response, and set headers for a
        conditional request, if possible.

        Used after fetching a cached response, but before potentially sending a new request.
        """
        # Determine if we need to send a new request or respond with an error
        is_expired = getattr(cached_response, 'is_expired', False)
        invalid_response = cached_response is None or is_expired
        if invalid_response and self._settings.only_if_cached and not self._settings.stale_if_error:
            self.error_504 = True
        elif cached_response is None:
            self.send_request = True
        elif is_expired and not (self._settings.only_if_cached and self._settings.stale_if_error):
            self.resend_request = True

        if cached_response is not None:
            self._update_validation_headers(cached_response)

    def _update_validation_headers(self, response: CachedResponse):
        # Revalidation may be triggered by either stale response or request/cached response headers
        directives = get_cache_directives(response.headers)
        revalidate = _has_validator(response.headers) and any(
            [
                response.is_expired,
                self._settings.revalidate,
                'no-cache' in directives,
                'must-revalidate' in directives and directives.get('max-age') == 0,
            ]
        )

        # Add the appropriate validation headers, if needed
        if revalidate:
            self.send_request = True
            if response.headers.get('ETag'):
                self._validation_headers['If-None-Match'] = response.headers['ETag']
            if response.headers.get('Last-Modified'):
                self._validation_headers['If-Modified-Since'] = response.headers['Last-Modified']

    def update_from_response(self, response: Response):
        """Update expiration + actions based on headers and other details from a new response.

        Used after receiving a new response, but before saving it to the cache.
        """
        if self._settings.cache_control:
            self._update_from_response_headers(response)

        # If "expired" but there's a validator, save it to the cache and revalidate on use
        expire_immediately = try_int(self.expire_after) == DO_NOT_CACHE
        has_validator = _has_validator(response.headers)
        self.skip_write = self.skip_write or (expire_immediately and not has_validator)

        # Apply filter callback, if any
        callback = self._settings.filter_fn
        filtered_out = callback is not None and not callback(response)

        # Apply and log remaining checks needed to determine if the response should be cached
        cache_criteria = {
            'disabled cache': self._settings.disabled,
            'disabled method': str(response.request.method) not in self._settings.allowable_methods,
            'disabled status': response.status_code not in self._settings.allowable_codes,
            'disabled by filter': filtered_out,
            'disabled by headers or expiration params': self.skip_write,
        }
        logger.debug(f'Pre-cache checks for response from {response.url}: {cache_criteria}')
        self.skip_write = any(cache_criteria.values())

    def _update_from_response_headers(self, response: Response):
        """Check response headers for expiration and other cache directives"""
        directives = get_cache_directives(response.headers)
        logger.debug(f'Cache directives from response headers: {directives}')

        if directives.get('immutable'):
            self.expire_after = NEVER_EXPIRE
        else:
            self.expire_after = coalesce(
                directives.get('max-age'),
                directives.get('expires'),
                self.expire_after,
            )
        self.skip_write = self.skip_write or 'no-store' in directives

    def update_request(self, request: PreparedRequest) -> PreparedRequest:
        """Apply validation headers (if any) before sending a request"""
        request.headers.update(self._validation_headers)
        return request

    def update_revalidated_response(
        self, response: Response, cached_response: CachedResponse
    ) -> CachedResponse:
        """After revalidation, update the cached response's headers and reset its expiration"""
        logger.debug(
            f'Response for URL {response.request.url} has not been modified; updating and using cached response'
        )
        cached_response.expires = self.expires
        cached_response.headers.update(response.headers)
        self.update_from_response(cached_response)
        return cached_response


def append_directive(
    headers: Optional[MutableMapping[str, str]], directive: str
) -> MutableMapping[str, str]:
    """Append a Cache-Control directive to existing headers (if any)"""
    headers = CaseInsensitiveDict(headers)
    directives = headers['Cache-Control'].split(',') if headers.get('Cache-Control') else []
    directives.append(directive)
    headers['Cache-Control'] = ','.join(directives)
    return headers


def get_cache_directives(headers: MutableMapping) -> Dict[str, CacheDirective]:
    """Get all Cache-Control directives as a dict. Handle duplicate headers and comma-separated
    lists. Key-only directives are returned as ``{key: True}``.
    """
    if not headers:
        return {}

    kv_directives = {}
    if headers.get('Cache-Control'):
        cache_directives = headers['Cache-Control'].split(',')
        kv_directives = dict([_split_kv_directive(value) for value in cache_directives])

    if 'Expires' in headers:
        kv_directives['expires'] = headers['Expires']
    return kv_directives


def _split_kv_directive(header_value: str) -> Tuple[str, CacheDirective]:
    """Split a cache directive into a ``(key, int)`` pair, if possible; otherwise just
    ``(key, True)``.
    """
    header_value = header_value.strip()
    if '=' in header_value:
        k, v = header_value.split('=', 1)
        return k, try_int(v)
    else:
        return header_value, True


def _has_validator(headers: MutableMapping) -> bool:
    return bool(headers.get('ETag') or headers.get('Last-Modified'))
