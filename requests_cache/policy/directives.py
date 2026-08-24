from datetime import timedelta
from typing import Optional, Union

from attrs import define, field
from requests.structures import CaseInsensitiveDict

from .._utils import decode, get_valid_kwargs, try_int
from ..models import RichMixin
from . import DO_NOT_CACHE, ExpirationTime, HeaderDict, get_expiration_seconds


def _int_or_bool(value):
    """Convert a cache directive value to an int, keeping ``True`` for value-less directives like
    ``stale-while-revalidate`` (with no ``=seconds`` part).
    """
    if value is True:
        return True
    return try_int(value)


@define(repr=False)
class CacheDirectives(RichMixin):
    """Parses Cache-Control directives and other relevant cache settings from either request or
    response headers
    """

    expires: str = field(default=None)
    immutable: bool = field(default=False)
    max_age: int = field(default=None, converter=try_int)
    max_stale: int = field(default=None, converter=try_int)
    min_fresh: int = field(default=None, converter=try_int)
    must_revalidate: bool = field(default=False)
    no_cache: bool = field(default=False)
    no_store: bool = field(default=False)
    actual_no_cache: bool = field(default=False)  # Nonstandard value/internal use only
    only_if_cached: bool = field(default=False)
    stale_if_error: Union[bool, int] = field(default=None, converter=_int_or_bool)
    stale_while_revalidate: Union[bool, int] = field(default=None, converter=_int_or_bool)
    etag: str = field(default=None)
    last_modified: str = field(default=None)

    @classmethod
    def from_headers(cls, headers: HeaderDict):
        """Parse cache directives and other settings from request or response headers"""
        headers = CaseInsensitiveDict(headers)
        directives = decode(headers.get('Cache-Control', '')).split(',')
        kv_directives = dict(_split_kv_directive(value) for value in directives)
        kwargs = get_valid_kwargs(
            cls.__init__, {k.replace('-', '_'): v for k, v in kv_directives.items()}
        )

        kwargs['actual_no_cache'] = headers.pop('X-ACTUAL-NO-CACHE', False)
        kwargs['expires'] = headers.get('Expires')
        kwargs['etag'] = headers.get('ETag')
        kwargs['last_modified'] = headers.get('Last-Modified')
        return cls(**kwargs)

    def get_expire_offset(self) -> timedelta:
        """Return the time offset to use for expiration, if either min-fresh or max-stale is set"""
        offset_seconds = 0
        if self.max_stale:
            offset_seconds = self.max_stale
        elif self.min_fresh:
            offset_seconds = -self.min_fresh
        return timedelta(seconds=offset_seconds)

    @property
    def has_validator(self) -> bool:
        return bool(self.etag or self.last_modified)


def _split_kv_directive(directive: str):
    """Split a cache directive into a `(key, value)` pair, or `(key, True)` if value-only"""
    directive = directive.strip().lower()
    return directive.split('=', 1) if '=' in directive else (directive, True)


def set_request_headers(
    headers: Optional[HeaderDict],
    expire_after,
    only_if_cached,
    refresh,
    force_refresh,
    stale_if_error: Union[bool, ExpirationTime] = None,
    stale_while_revalidate: Union[bool, ExpirationTime] = None,
):
    """Translate keyword arguments into equivalent request headers"""
    headers = CaseInsensitiveDict(headers)
    directives = headers['Cache-Control'].split(',') if headers.get('Cache-Control') else []

    if only_if_cached:
        directives.append('only-if-cached')
    if refresh:
        directives.append('must-revalidate')
    if force_refresh:
        directives.append('no-cache')
    _append_stale_directive(directives, 'stale-if-error', stale_if_error)
    _append_stale_directive(directives, 'stale-while-revalidate', stale_while_revalidate)

    # Handle custom value to completely skip the cache; much be passed via headers to make the
    # round trip from CachedSession.request() -> Session.request() -> CachedSession.send()
    if expire_after == DO_NOT_CACHE:
        headers['X-ACTUAL-NO-CACHE'] = 'true'
    elif expire_after is not None:
        directives.append(f'max-age={get_expiration_seconds(expire_after)}')

    if directives:
        headers['Cache-Control'] = ','.join(sorted(set(directives)))
    return headers


def _append_stale_directive(directives, name, value):
    """Encode a per-request ``stale_if_error`` / ``stale_while_revalidate`` value as a Cache-Control
    directive. A time value becomes ``name=<seconds>``, and ``True`` becomes a value-less directive.
    ``None`` (and ``False``) are left off so the session-level setting still applies.
    """
    if value is None or value is False:
        return
    if value is True:
        directives.append(name)
    else:
        directives.append(f'{name}={get_expiration_seconds(value)}')
