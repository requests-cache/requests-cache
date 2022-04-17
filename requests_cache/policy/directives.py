from typing import Optional

from attr import define, field
from requests.models import CaseInsensitiveDict

from .._utils import get_valid_kwargs, try_int
from . import HeaderDict, get_expiration_seconds


@define
class CacheDirectives:
    """Parses Cache-Control directives and other relevant cache settings from either request or
    response headers
    """

    expires: str = field(default=None)
    immutable: bool = field(default=False)
    max_age: int = field(default=None, converter=try_int)
    must_revalidate: bool = field(default=False)
    no_cache: bool = field(default=False)
    no_store: bool = field(default=False)
    only_if_cached: bool = field(default=False)
    etag: str = field(default=None)
    last_modified: str = field(default=None)

    # Not yet implemented:
    # max_stale: int = field(default=None, converter=try_int)
    # min_fresh: int = field(default=None, converter=try_int)
    # stale_if_error: int = field(default=None, converter=try_int)
    # stale_while_revalidate: bool = field(default=False)

    @classmethod
    def from_headers(cls, headers: HeaderDict):
        """Parse cache directives and other settings from request or response headers"""
        headers = CaseInsensitiveDict(headers)
        directives = headers.get('Cache-Control', '').split(',')
        kv_directives = dict(_split_kv_directive(value) for value in directives)
        kwargs = get_valid_kwargs(
            cls.__init__, {k.replace('-', '_'): v for k, v in kv_directives.items()}
        )

        kwargs['expires'] = headers.get('Expires')
        kwargs['etag'] = headers.get('ETag')
        kwargs['last_modified'] = headers.get('Last-Modified')
        return cls(**kwargs)

    # def to_dict(self) -> CaseInsensitiveDict:
    #     return {k.title().replace('_', '-'): v for k, v in asdict(self).items() if v is not None}

    @property
    def has_validator(self) -> bool:
        return bool(self.etag or self.last_modified)


def _split_kv_directive(directive: str):
    """Split a cache directive into a `(key, value)` pair, or `(key, True)` if value-only"""
    directive = directive.strip().lower()
    return directive.split('=', 1) if '=' in directive else (directive, True)


def set_request_headers(
    headers: Optional[HeaderDict], expire_after, only_if_cached, refresh, force_refresh
):
    """Translate keyword arguments into equivalent request headers"""
    headers = CaseInsensitiveDict(headers)
    directives = headers['Cache-Control'].split(',') if headers.get('Cache-Control') else []

    if expire_after is not None:
        directives.append(f'max-age={get_expiration_seconds(expire_after)}')
    if only_if_cached:
        directives.append('only-if-cached')
    if refresh:
        directives.append('must-revalidate')
    if force_refresh:
        directives.append('no-cache')

    if directives:
        headers['Cache-Control'] = ','.join(directives)
    return headers
