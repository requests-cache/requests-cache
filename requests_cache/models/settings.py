from typing import TYPE_CHECKING, Callable, Dict, Iterable, Union

from attr import asdict, define, field

from .._utils import get_valid_kwargs
from ..expiration import ExpirationTime

if TYPE_CHECKING:
    from . import AnyResponse

# Signatures for user-provided callbacks
FilterCallback = Callable[['AnyResponse'], bool]
KeyCallback = Callable[..., str]


# TODO: RequestSettings subclass?
#   This would work by merging settings for an individual request on top of session settings
#   This would also allow for *any* session setting to be passed as a per-request setting
#   ...But only for send(), not request()
# TODO: HeaderSettings class?
#   This would encapsulate settings from Cache-Control directives and other cache headers
#   Downside: that logic would then live in this moduel instead of in cache_control (which may be a better fit)


@define(init=False)
class CacheSettings:
    """Settings that affect caching behavior, used by :py:class:`.CachedSession` and
    :py:class:`.BaseCache`.

    Args:
        allowable_codes: Only cache responses with one of these status codes
        allowable_methods: Cache only responses for one of these HTTP methods
        cache_control: Use Cache-Control and other response headers to set expiration
        expire_after: Time after which cached items will expire
        filter_fn: Response filtering function that indicates whether or not a given response should
            be cached.
        ignored_parameters: List of request parameters to not match against, and exclude from the cache
        key_fn: Request matching function for generating custom cache keys
        match_headers: Match request headers when reading from the cache; may be either ``True`` or
            a list of specific headers to match
        stale_if_error: Return stale cache data if a new request raises an exception
        urls_expire_after: Expiration times to apply for different URL patterns
    """

    allowable_codes: Iterable[int] = field(default=(200,))
    allowable_methods: Iterable[str] = field(default=('GET', 'HEAD'))
    cache_control: bool = field(default=False)
    disabled: bool = field(default=False)
    expire_after: ExpirationTime = field(default=-1)
    filter_fn: FilterCallback = field(default=None)
    ignored_parameters: Iterable[str] = field(default=None)
    key_fn: KeyCallback = field(default=None)
    match_headers: Union[Iterable[str], bool] = field(default=False)
    only_if_cached: bool = field(default=False)
    stale_if_error: bool = field(default=False)
    urls_expire_after: Dict[str, ExpirationTime] = field(factory=dict)

    def __init__(self, **kwargs):
        # Backwards-compatibility for old argument names
        if 'old_data_on_error' in kwargs:
            kwargs['stale_if_error'] = kwargs.pop('old_data_on_error')
        if 'include_get_headers' in kwargs:
            kwargs['match_headers'] = kwargs.pop('include_get_headers')

        # Ignore invalid kwargs for easier initialization from mixed **kwargs
        kwargs = get_valid_kwargs(self.__attrs_init__, kwargs)
        self.__attrs_init__(**kwargs)


@define(init=False)
class RequestSettings(CacheSettings):
    """Cache settings that may be set for an individual request"""

    refresh: bool = field(default=False)
    revalidate: bool = field(default=False)
    request_expire_after: ExpirationTime = field(default=-1)

    def __init__(self, session_settings: CacheSettings, **kwargs):
        # Start with session-level cache settings and add/override with request-level settings
        kwargs['request_expire_after'] = kwargs.pop('expire_after', None)
        kwargs = {**asdict(session_settings), **kwargs}
        super().__init__(**kwargs)
