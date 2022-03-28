from typing import TYPE_CHECKING, Callable, Dict, Iterable, Union

from attr import asdict, define, field

from ._utils import get_valid_kwargs
from .expiration import ExpirationTime

if TYPE_CHECKING:
    from .models import AnyResponse

ALL_METHODS = ('GET', 'HEAD', 'OPTIONS', 'POST', 'PUT', 'PATCH', 'DELETE')
DEFAULT_CACHE_NAME = 'http_cache'
DEFAULT_METHODS = ('GET', 'HEAD')
DEFAULT_STATUS_CODES = (200,)

# Signatures for user-provided callbacks
FilterCallback = Callable[['AnyResponse'], bool]
KeyCallback = Callable[..., str]


@define(init=False)
class CacheSettings:
    """Class used internally to store settings that affect caching behavior. This allows settings
    to be used across multiple modules, but exposed to the user in a single property
    (:py:attr:`.CachedSession.settings`). These values can safely be modified after initialization. See
    :py:class:`.CachedSession` and :ref:`user-guide` for usage details.
    """

    allowable_codes: Iterable[int] = field(default=DEFAULT_STATUS_CODES)
    allowable_methods: Iterable[str] = field(default=DEFAULT_METHODS)
    cache_control: bool = field(default=False)
    disabled: bool = field(default=False)
    expire_after: ExpirationTime = field(default=None)
    filter_fn: FilterCallback = field(default=None)
    ignored_parameters: Iterable[str] = field(default=None)
    key_fn: KeyCallback = field(default=None)
    match_headers: Union[Iterable[str], bool] = field(default=False)
    only_if_cached: bool = field(default=False)
    stale_if_error: bool = field(default=False)
    urls_expire_after: Dict[str, ExpirationTime] = field(factory=dict)

    # Additional settings that may be set for an individual request; not used at session level
    refresh: bool = field(default=False)
    revalidate: bool = field(default=False)
    request_expire_after: ExpirationTime = field(default=None)

    def __init__(self, **kwargs):
        """Ignore invalid kwargs for easier initialization from mixed ``**kwargs``"""
        kwargs = self._rename_kwargs(kwargs)
        kwargs = get_valid_kwargs(self.__attrs_init__, kwargs)
        self.__attrs_init__(**kwargs)

    @staticmethod
    def _rename_kwargs(kwargs):
        """Handle some deprecated argument names"""
        if 'old_data_on_error' in kwargs:
            kwargs['stale_if_error'] = kwargs.pop('old_data_on_error')
        if 'include_get_headers' in kwargs:
            kwargs['match_headers'] = kwargs.pop('include_get_headers')
        return kwargs


@define(init=False)
class RequestSettings(CacheSettings):
    """Cache settings that may be set for an individual request"""

    def __init__(self, session_settings: CacheSettings = None, **kwargs):
        """Start with session-level cache settings and append/override with request-level settings"""
        session_kwargs = asdict(session_settings) if session_settings else {}
        # request-level expiration needs to be stored separately
        kwargs['request_expire_after'] = kwargs.pop('expire_after', None)
        super().__init__(**{**session_kwargs, **kwargs})
