"""Utilities for determining cache expiration and other cache actions"""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from fnmatch import fnmatch
from logging import getLogger
from typing import Any, Dict, Mapping, Optional, Tuple, Union

from requests import PreparedRequest, Response

# Value that may be set by either Cache-Control headers or CachedSession params to disable caching
DO_NOT_CACHE = 0

# Currently supported Cache-Control directives
CACHE_DIRECTIVES = ['max-age', 'no-cache', 'no-store']

# All cache-related headers, for logging/reference; not all are supported
REQUEST_CACHE_HEADERS = [
    'Cache-Control',
    'If-Unmodified-Since',
    'If-Modified-Since',
    'If-Match',
    'If-None-Match',
]
RESPONSE_CACHE_HEADERS = ['Cache-Control', 'ETag', 'Expires', 'Age']

CacheDirective = Tuple[str, Union[None, int, bool]]
ExpirationTime = Union[None, int, float, str, datetime, timedelta]
ExpirationPatterns = Dict[str, ExpirationTime]
logger = getLogger(__name__)


class CacheActions:
    """A dataclass that contains info on specific actions to take for a given cache item.
    This is determined by a combination of cache settings and request + response headers.
    If multiple sources are provided, they will be used in the following order of precedence:

    1. Cache-Control request headers (if enabled)
    2. Cache-Control response headers (if enabled)
    3. Per-request expiration
    4. Per-URL expiration
    5. Per-session expiration
    """

    def __init__(
        self,
        cache_key: str,
        request: PreparedRequest,
        cache_control: bool = False,
        **kwargs,
    ):
        """Initialize from request info and cache settings"""
        self.cache_key = cache_key
        self.cache_control = cache_control
        if cache_control and has_cache_headers(request.headers):
            self._init_from_headers(request.headers)
        else:
            self._init_from_settings(url=request.url, **kwargs)

    def _init_from_headers(self, headers: Mapping):
        """Initialize from request headers"""
        directives = get_cache_directives(headers)
        do_not_cache = directives.get('max-age') == DO_NOT_CACHE
        self.expire_after = directives.get('max-age')
        self.skip_read = do_not_cache or 'no-store' in directives or 'no-cache' in directives
        self.skip_write = do_not_cache or 'no-store' in directives

    def _init_from_settings(
        self,
        url: str = None,
        request_expire_after: ExpirationTime = None,
        session_expire_after: ExpirationTime = None,
        urls_expire_after: ExpirationPatterns = None,
        **kwargs,
    ):
        """Initialize from cache settings"""
        # Check expire_after values in order of precedence
        expire_after = coalesce(
            request_expire_after,
            get_url_expiration(url, urls_expire_after),
            session_expire_after,
        )

        do_not_cache = expire_after == DO_NOT_CACHE
        self.expire_after = expire_after
        self.skip_read = do_not_cache
        self.skip_write = do_not_cache

    @property
    def expires(self) -> Optional[datetime]:
        """Convert the user/header-provided expiration value to a datetime"""
        return get_expiration_datetime(self.expire_after)

    def update_from_response(self, response: Response):
        """Update expiration + actions based on response headers, if not previously set by request"""
        if not self.cache_control:
            return
        directives = get_cache_directives(response.headers)
        do_not_cache = directives.get('max-age') == DO_NOT_CACHE
        self.expire_after = coalesce(self.expires, directives.get('max-age'), directives.get('expires'))
        self.skip_write = self.skip_write or do_not_cache or 'no-store' in directives

    def __str__(self):
        return (
            f'Expire after: {self.expire_after} | Skip read: {self.skip_read} | '
            f'Skip write: {self.skip_write}'
        )


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


def has_cache_headers(headers: Mapping) -> bool:
    """Determine if headers contain cache directives **that we currently support**"""
    has_cache_control = any([d in headers.get('Cache-Control', '') for d in CACHE_DIRECTIVES])
    return has_cache_control or bool(headers.get('Expires'))


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
