"""Internal utilities for determining cache expiration and other cache actions.

.. automodsumm:: requests_cache.cache_control
   :classes-only:
   :nosignatures:

.. automodsumm:: requests_cache.cache_control
   :functions-only:
   :nosignatures:
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from fnmatch import fnmatch
from logging import getLogger
from math import ceil
from typing import TYPE_CHECKING, Any, Dict, Mapping, Optional, Tuple, Union

from attr import define, field
from requests import PreparedRequest, Response

if TYPE_CHECKING:
    from .models import CachedResponse

__all__ = ['DO_NOT_CACHE', 'CacheActions']
# May be set by either headers or expire_after param to disable caching
DO_NOT_CACHE = 0
# Supported Cache-Control directives
CACHE_DIRECTIVES = ['max-age', 'no-cache', 'no-store']

CacheDirective = Tuple[str, Union[None, int, bool]]
ExpirationTime = Union[None, int, float, str, datetime, timedelta]
ExpirationPatterns = Dict[str, ExpirationTime]

logger = getLogger(__name__)


@define
class CacheActions:
    """A class that translates cache settings and headers into specific actions to take for a
    given cache item. Actions include:

    * Reading from the cache
    * Writing to the cache
    * Setting cache expiration
    * Adding request headers

    If multiple sources provide an expiration time, they will be used in the following order of
    precedence:

    1. Cache-Control request headers
    2. Cache-Control response headers (if enabled)
    3. Per-request expiration
    4. Per-URL expiration
    5. Per-session expiration
    """

    cache_control: bool = field(default=False)
    cache_key: str = field(default=None)
    expire_after: ExpirationTime = field(default=None)
    request_headers: Dict[str, str] = field(factory=dict)
    skip_read: bool = field(default=False)
    skip_write: bool = field(default=False)

    @classmethod
    def from_request(
        cls,
        cache_key: str,
        request: PreparedRequest,
        cache_control: bool = False,
        session_expire_after: ExpirationTime = None,
        urls_expire_after: ExpirationPatterns = None,
        request_expire_after: ExpirationTime = None,
        **kwargs,
    ):
        """Initialize from request info and cache settings"""
        # Check expire_after values in order of precedence
        directives = get_cache_directives(request.headers)
        expire_after = coalesce(
            directives.get('max-age'),
            request_expire_after,
            get_url_expiration(request.url, urls_expire_after),
            session_expire_after,
        )
        do_not_cache = expire_after == DO_NOT_CACHE

        return cls(
            cache_control=cache_control,
            cache_key=cache_key,
            expire_after=expire_after,
            skip_read=do_not_cache or 'no-store' in directives or 'no-cache' in directives,
            skip_write=do_not_cache or 'no-store' in directives,
        )

    @property
    def expires(self) -> Optional[datetime]:
        """Convert the user/header-provided expiration value to a datetime"""
        return get_expiration_datetime(self.expire_after)

    def update_from_cached_response(self, response: CachedResponse):
        """Check for relevant cache headers on a cached response, and set corresponding request
        headers for a conditional request, if possible.

        Used after fetching a cached response, but before potentially sending a new request
        (if expired).
        """
        if not response or not response.is_expired:
            return

        if response.headers.get('ETag'):
            self.request_headers['If-None-Match'] = response.headers['ETag']
        if response.headers.get('Last-Modified'):
            self.request_headers['If-Modified-Since'] = response.headers['Last-Modified']
        self.request_headers = {k: v for k, v in self.request_headers.items() if v}

    def update_from_response(self, response: Response):
        """Update expiration + actions based on response headers, if not previously set.

        Used after receiving a new response but before saving it to the cache.
        """
        if not self.cache_control or not response:
            return

        directives = get_cache_directives(response.headers)
        do_not_cache = directives.get('max-age') == DO_NOT_CACHE
        self.expire_after = coalesce(
            directives.get('max-age'), directives.get('expires'), self.expire_after
        )
        self.skip_write = self.skip_write or do_not_cache or 'no-store' in directives


def coalesce(*values: Any, default=None) -> Any:
    """Get the first non-``None`` value in a list of values"""
    return next((v for v in values if v is not None), default)


def get_expiration_datetime(expire_after: ExpirationTime) -> Optional[datetime]:
    """Convert an expiration value in any supported format to an absolute datetime"""
    # Never expire
    if expire_after is None or expire_after == -1:
        return None
    # Expire immediately
    elif expire_after == DO_NOT_CACHE:
        return datetime.utcnow()
    # Already a datetime or datetime str
    if isinstance(expire_after, str):
        expire_after = parse_http_date(expire_after)
        return to_utc(expire_after) if expire_after else None
    elif isinstance(expire_after, datetime):
        return to_utc(expire_after)

    # Otherwise, it must be a timedelta or time in seconds
    if not isinstance(expire_after, timedelta):
        expire_after = timedelta(seconds=expire_after)
    return datetime.utcnow() + expire_after


def get_expiration_seconds(expire_after: ExpirationTime) -> Optional[int]:
    """Convert an expiration value in any supported format to an expiration time in seconds"""
    expires = get_expiration_datetime(expire_after)
    return ceil((expires - datetime.utcnow()).total_seconds()) if expires else None


def get_cache_directives(headers: Mapping) -> Dict:
    """Get all Cache-Control directives, and handle multiple headers and comma-separated lists"""
    if not headers:
        return {}

    cache_directives = headers.get('Cache-Control', '').split(',')
    kv_directives = dict([split_kv_directive(value) for value in cache_directives])

    if 'Expires' in headers:
        kv_directives['expires'] = headers['Expires']
    return kv_directives


def get_url_expiration(
    url: Optional[str], urls_expire_after: ExpirationPatterns = None
) -> ExpirationTime:
    """Check for a matching per-URL expiration, if any"""
    if not url:
        return None

    for pattern, expire_after in (urls_expire_after or {}).items():
        if url_match(url, pattern):
            logger.debug(f'URL {url} matched pattern "{pattern}": {expire_after}')
            return expire_after
    return None


def parse_http_date(value: str) -> Optional[datetime]:
    """Attempt to parse an HTTP (RFC 5322-compatible) timestamp"""
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        logger.debug(f'Failed to parse timestamp: {value}')
        return None


def split_kv_directive(header_value: str) -> CacheDirective:
    """Split a cache directive into a ``(header_value, int)`` key-value pair, if possible;
    otherwise just ``(header_value, True)``.
    """
    header_value = header_value.strip()
    if '=' in header_value:
        k, v = header_value.split('=', 1)
        return k, try_int(v)
    else:
        return header_value, True


def to_utc(dt: datetime):
    """All internal datetimes are UTC and timezone-naive. Convert any user/header-provided
    datetimes to the same format.
    """
    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc)
        dt = dt.replace(tzinfo=None)
    return dt


def try_int(value: Optional[str]) -> Optional[int]:
    """Convert a string value to an int, if possible, otherwise ``None``"""
    return int(str(value)) if str(value).isnumeric() else None


def url_match(url: str, pattern: str) -> bool:
    """Determine if a URL matches a pattern

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
    url = url.split('://')[-1]
    pattern = pattern.split('://')[-1].rstrip('*') + '**'
    return fnmatch(url, pattern)
