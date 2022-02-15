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

from ._utils import coalesce

if TYPE_CHECKING:
    from .models import CachedResponse

__all__ = ['DO_NOT_CACHE', 'CacheActions']

# May be set by either headers or expire_after param to disable caching or disable expiration
DO_NOT_CACHE = 0
NEVER_EXPIRE = -1
# Supported Cache-Control directives
CACHE_DIRECTIVES = ['immutable', 'max-age', 'no-cache', 'no-store']

CacheDirective = Tuple[str, Union[None, int, bool]]
ExpirationTime = Union[None, int, float, str, datetime, timedelta]
ExpirationPatterns = Dict[str, ExpirationTime]

logger = getLogger(__name__)


@define
class CacheActions:
    """A class that translates cache settings and headers into specific actions to take for a
    given cache item. Actions include:

    * Read from the cache
    * Write to the cache
    * Set cache expiration
    * Add headers for conditional requests

    If multiple sources provide an expiration time, they will be used in the following order of
    precedence:

    1. Cache-Control request headers
    2. Cache-Control response headers (if enabled)
    3. Per-request expiration
    4. Per-URL expiration
    5. Per-session expiration

    See :ref:`headers` for more details about behavior.
    """

    cache_control: bool = field(default=False)
    cache_key: str = field(default=None)
    expire_after: ExpirationTime = field(default=None)
    request_directives: Dict[str, str] = field(factory=dict)
    skip_read: bool = field(default=False)
    skip_write: bool = field(default=False)
    validation_headers: Dict[str, str] = field(factory=dict)

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
        directives = get_cache_directives(request.headers)
        logger.debug(f'Cache directives from request headers: {directives}')

        # Check expiration values in order of precedence
        expire_after = coalesce(
            directives.get('max-age'),
            request_expire_after,
            get_url_expiration(request.url, urls_expire_after),
            session_expire_after,
        )

        # Check conditions for caching based on request headers. Also check expire_after options
        # unless cache_control=True, in which case these may be overridden by response headers.
        check_expiration = directives.get('max-age') if cache_control else expire_after
        skip_write = check_expiration == DO_NOT_CACHE or 'no-store' in directives

        return cls(
            cache_control=cache_control,
            cache_key=cache_key,
            expire_after=expire_after,
            request_directives=directives,
            skip_read=skip_write or 'no-cache' in directives,
            skip_write=skip_write,
        )

    @property
    def expires(self) -> Optional[datetime]:
        """Convert the user/header-provided expiration value to a datetime"""
        return get_expiration_datetime(self.expire_after)

    def update_from_cached_response(self, response: CachedResponse):
        """Check for relevant cache headers from a cached response, and set headers for a
        conditional request, if possible.

        Used after fetching a cached response, but before potentially sending a new request
        (if expired).
        """
        if not response or not response.is_expired:
            return

        if response.headers.get('ETag'):
            self.validation_headers['If-None-Match'] = response.headers['ETag']
        if response.headers.get('Last-Modified'):
            self.validation_headers['If-Modified-Since'] = response.headers['Last-Modified']

    def update_from_response(self, response: Response):
        """Update expiration + actions based on headers from a new response.

        Used after receiving a new response but before saving it to the cache.
        """
        if not response or not self.cache_control:
            return

        directives = get_cache_directives(response.headers)
        logger.debug(f'Cache directives from response headers: {directives}')

        # Check headers for expiration, validators, and other cache directives
        if directives.get('immutable'):
            self.expire_after = NEVER_EXPIRE
        else:
            self.expire_after = coalesce(
                directives.get('max-age'), directives.get('expires'), self.expire_after
            )
        has_validator = response.headers.get('ETag') or response.headers.get('Last-Modified')
        no_store = 'no-store' in directives or 'no-store' in self.request_directives

        # If expiration is 0 and there's a validator, save it to the cache and revalidate on use
        # Otherwise, skip writing to the cache if specified by expiration or other headers
        expire_immediately = try_int(self.expire_after) == DO_NOT_CACHE
        self.skip_write = (expire_immediately or no_store) and not has_validator


def get_expiration_datetime(expire_after: ExpirationTime) -> Optional[datetime]:
    """Convert an expiration value in any supported format to an absolute datetime"""
    # Never expire
    if expire_after is None or expire_after == NEVER_EXPIRE:
        return None
    # Expire immediately
    elif try_int(expire_after) == DO_NOT_CACHE:
        return datetime.utcnow()
    # Already a datetime or datetime str
    if isinstance(expire_after, str):
        return parse_http_date(expire_after)
    elif isinstance(expire_after, datetime):
        return to_utc(expire_after)

    # Otherwise, it must be a timedelta or time in seconds
    if not isinstance(expire_after, timedelta):
        expire_after = timedelta(seconds=expire_after)
    return datetime.utcnow() + expire_after


def get_expiration_seconds(expire_after: ExpirationTime) -> int:
    """Convert an expiration value in any supported format to an expiration time in seconds"""
    expires = get_expiration_datetime(expire_after)
    return ceil((expires - datetime.utcnow()).total_seconds()) if expires else NEVER_EXPIRE


def get_cache_directives(headers: Mapping) -> Dict:
    """Get all Cache-Control directives, and handle multiple headers and comma-separated lists"""
    if not headers:
        return {}

    kv_directives = {}
    if headers.get('Cache-Control'):
        cache_directives = headers['Cache-Control'].split(',')
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
        expire_after = parsedate_to_datetime(value)
        return to_utc(expire_after)
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


def try_int(value: Any) -> Optional[int]:
    """Convert a value to an int, if possible, otherwise ``None``"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
