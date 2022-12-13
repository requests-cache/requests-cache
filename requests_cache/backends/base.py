"""Base classes for all cache backends.

.. automodsumm:: requests_cache.backends.base
   :classes-only:
   :nosignatures:
"""
import pickle
from abc import ABC
from collections import UserDict
from collections.abc import MutableMapping
from datetime import datetime
from logging import getLogger
from typing import Callable, Iterable, Iterator, List, Optional, Union
from warnings import warn

from requests import Request

from ..cache_keys import create_key, redact_response
from ..models import AnyRequest, AnyResponse, CachedResponse
from ..policy import ExpirationTime, get_expiration_datetime
from ..serializers import init_serializer

# Specific exceptions that may be raised during deserialization
DESERIALIZE_ERRORS = (AttributeError, ImportError, TypeError, ValueError, pickle.PickleError)

# Signature for user-provided callback
KEY_FN = Callable[..., str]

ResponseOrKey = Union[CachedResponse, str]
logger = getLogger(__name__)


class BaseCache:
    """Base class for cache backends. Can be used as a non-persistent, in-memory cache.

    This manages higher-level cache operations, including:

    * Cache expiration
    * Generating cache keys
    * Managing redirect history
    * Convenience methods for general cache info

    Lower-level storage operations are handled by :py:class:`.BaseStorage`.

    To extend this with your own custom backend, see :ref:`custom-backends`.
    """

    def __init__(
        self,
        cache_name: str = 'http_cache',
        match_headers: Union[Iterable[str], bool] = False,
        ignored_parameters: Iterable[str] = None,
        key_fn: KEY_FN = None,
        **kwargs,
    ):
        self.responses: BaseStorage = DictStorage()
        self.redirects: BaseStorage = DictStorage()
        self.cache_name = cache_name
        self.ignored_parameters = ignored_parameters
        self.key_fn = key_fn or create_key
        self.match_headers = match_headers or kwargs.pop('include_get_headers', False)

    @property
    def urls(self) -> Iterator[str]:
        """Get all URLs currently in the cache (excluding redirects)"""
        for key in self.responses:
            try:
                yield self.responses[key].url
            except DESERIALIZE_ERRORS:
                pass

    def get_response(self, key: str, default=None) -> Optional[CachedResponse]:
        """Retrieve a response from the cache, if it exists

        Args:
            key: Cache key for the response
            default: Value to return if `key` is not in the cache
        """
        try:
            response = self.responses.get(key)
            if response is None:  # Note: bool(requests.Response) is False if status > 400
                response = self.responses[self.redirects[key]]
            response.cache_key = key
            return response
        except KeyError:
            return default
        except DESERIALIZE_ERRORS as e:
            logger.error(f'Unable to deserialize response with key {key}: {str(e)}')
            logger.debug(e, exc_info=True)
            return default

    def save_response(self, response: AnyResponse, cache_key: str = None, expires: datetime = None):
        """Save a response to the cache

        Args:
            cache_key: Cache key for this response; will otherwise be generated based on request
            response: Response to save
            expires: Absolute expiration time for this response
        """
        cache_key = cache_key or self.create_key(response.request)
        cached_response = CachedResponse.from_response(response, expires=expires)
        cached_response = redact_response(cached_response, self.ignored_parameters)
        self.responses[cache_key] = cached_response
        for r in response.history:
            self.redirects[self.create_key(r.request)] = cache_key

    def bulk_delete(self, keys: Iterable[str]):
        """Remove multiple responses and their associated redirects from the cache"""
        self.responses.bulk_delete(keys)
        # Remove any redirects that no longer point to an existing response
        invalid_redirects = [k for k, v in self.redirects.items() if v not in self.responses]
        self.redirects.bulk_delete(set(keys) | set(invalid_redirects))

    def clear(self):
        """Delete all items from the cache"""
        logger.info('Clearing all items from the cache')
        self.responses.clear()
        self.redirects.clear()

    def create_key(self, request: AnyRequest = None, **kwargs) -> str:
        """Create a normalized cache key from a request object"""
        return self.key_fn(
            request=request,
            ignored_parameters=self.ignored_parameters,
            match_headers=self.match_headers,
            **kwargs,
        )

    def contains(
        self,
        key: str = None,
        request: AnyRequest = None,
        url: str = None,
    ):
        """Check if the specified request is cached

        Args:
            key: Check for a specific cache key
            request: Check for a matching request, according to current request matching settings
            url: Check for a matching GET request with the specified URL
        """
        if url:
            request = Request('GET', url)
        if request and not key:
            key = self.create_key(request)
        return key in self.responses or key in self.redirects

    def delete(
        self,
        *keys: str,
        expired: bool = False,
        invalid: bool = False,
        requests: Iterable[AnyRequest] = None,
        urls: Iterable[str] = None,
    ):
        """Remove responses from the cache according one or more conditions.

        Args:
            keys: Remove responses with these cache keys
            expired: Remove all expired responses
            invalid: Remove all invalid responses (that can't be deserialized with current settings)
            requests: Remove matching responses, according to current request matching settings
            urls: Remove matching GET requests for the specified URL(s)
        """
        delete_keys: List[str] = list(keys) if keys else []
        if urls:
            requests = list(requests or []) + [Request('GET', url).prepare() for url in urls]
        if requests:
            delete_keys += [self.create_key(request) for request in requests]

        for response in self.filter(valid=False, expired=expired, invalid=invalid):
            if response.cache_key:
                delete_keys.append(response.cache_key)

        logger.debug(f'Deleting up to {len(delete_keys)} responses')
        self.responses.bulk_delete(delete_keys)
        self._prune_redirects()

    def _prune_redirects(self):
        """Remove any redirects that no longer point to an existing response"""
        invalid_redirects = [k for k, v in self.redirects.items() if v not in self.responses]
        self.redirects.bulk_delete(invalid_redirects)

    def filter(
        self,
        valid: bool = True,
        expired: bool = True,
        invalid: bool = False,
    ) -> Iterator[CachedResponse]:
        """Get responses from the cache, with optional filters

        Args:
            valid: Include valid and unexpired responses; set to ``False`` to get **only**
                expired/invalid/old responses
            expired: Include expired responses
            invalid: Include invalid responses (as an empty ``CachedResponse``)
        """
        if not any([valid, expired, invalid]):
            return
        for key in self.responses.keys():
            response = self.get_response(key)

            # Use an empty response as a placeholder for an invalid response, if specified
            if invalid and response is None:
                response = CachedResponse(status_code=504)
                response.cache_key = key
                yield response
            elif response is not None and (
                (valid and not response.is_expired) or (expired and response.is_expired)
            ):
                yield response

    def reset_expiration(self, expire_after: ExpirationTime = None):
        """Set a new expiration value on existing cache items

        Args:
            expire_after: New expiration value, **relative to the current time**
        """
        expires = get_expiration_datetime(expire_after)
        logger.info(f'Resetting expiration with: {expires}')
        for response in self.filter():
            response.expires = expires
            self.responses[response.cache_key] = response

    def update(self, other: 'BaseCache'):
        """Update this cache with the contents of another cache"""
        logger.debug(f'Copying {len(other.responses)} responses from {repr(other)} to {repr(self)}')
        self.responses.update(other.responses)
        self.redirects.update(other.redirects)

    def __str__(self):
        return f'<{self.__class__.__name__}(name={self.cache_name})>'

    def __repr__(self):
        return str(self)

    # Deprecated methods
    # --------------------

    def delete_url(self, url: str, method: str = 'GET', **kwargs):
        warn(
            'BaseCache.delete_url() is deprecated; please use .delete(urls=...) instead',
            DeprecationWarning,
        )
        self.delete(requests=[Request(method, url, **kwargs)])

    def delete_urls(self, urls: Iterable[str], method: str = 'GET', **kwargs):
        warn(
            'BaseCache.delete_urls() is deprecated; please use .delete(urls=...) instead',
            DeprecationWarning,
        )
        self.delete(requests=[Request(method, url, **kwargs) for url in urls])

    def has_key(self, key: str) -> bool:
        warn(
            'BaseCache.has_key() is deprecated; please use `key in cache.responses` instead',
            DeprecationWarning,
        )
        return key in self.responses

    def has_url(self, url: str, method: str = 'GET', **kwargs) -> bool:
        warn(
            'BaseCache.has_url() is deprecated; please use .contains(url=...) instead',
            DeprecationWarning,
        )
        return self.contains(request=Request(method, url, **kwargs))

    def keys(self, check_expiry: bool = False) -> Iterator[str]:
        warn(
            'BaseCache.keys() is deprecated; '
            'please use .filter() or BaseCache.responses.keys() instead',
            DeprecationWarning,
        )
        yield from self.redirects.keys()
        for response in self.filter(expired=not check_expiry):
            if response.cache_key:
                yield response.cache_key

    def response_count(self, check_expiry: bool = False) -> int:
        warn(
            'BaseCache.response_count() is deprecated; '
            'please use .filter() or len(BaseCache.responses) instead',
            DeprecationWarning,
        )
        return len(list(self.filter(expired=not check_expiry)))

    def remove_expired_responses(self, expire_after: ExpirationTime = None):
        warn(
            'BaseCache.remove_expired_responses() is deprecated; '
            'please use .delete(expired=True) instead',
            DeprecationWarning,
        )
        if expire_after:
            self.reset_expiration(expire_after)
        self.delete(expired=True, invalid=True)

    def values(self, check_expiry: bool = False) -> Iterator[CachedResponse]:
        warn('BaseCache.values() is deprecated; please use .filter() instead', DeprecationWarning)
        yield from self.filter(expired=not check_expiry)


class BaseStorage(MutableMapping, ABC):
    """Base class for backend storage implementations. This provides a common dictionary-like
    interface for the underlying storage operations (create, read, update, delete). One
    ``BaseStorage`` instance corresponds to a single table/hash/collection, or whatever the
    backend-specific equivalent may be.

    ``BaseStorage`` subclasses contain no behavior specific to ``requests`` or caching, which are
    handled by :py:class:`.BaseCache`.

    ``BaseStorage`` also contains a serializer module or instance (defaulting to :py:mod:`pickle`),
    which determines how :py:class:`.CachedResponse` objects are saved internally. See
    :ref:`serializers` for details.

    Args:
        serializer: Custom serializer that provides ``loads`` and ``dumps`` methods
        kwargs: Additional serializer or backend-specific keyword arguments
    """

    def __init__(
        self,
        serializer=None,
        **kwargs,
    ):
        self._serializer = init_serializer(serializer, **kwargs)
        logger.debug(f'Initializing {type(self).__name__} with serializer: {self.serializer}')

    @property
    def serializer(self):
        return self._serializer

    @serializer.setter
    def serializer(self, value):
        self._serializer = init_serializer(value)

    def bulk_delete(self, keys: Iterable[str]):
        """Delete multiple keys from the cache, without raising errors for missing keys. This is a
        naive implementation that subclasses should override with a more efficient backend-specific
        implementation, if possible.
        """
        for k in keys:
            try:
                del self[k]
            except KeyError:
                pass

    def __str__(self):
        return str(list(self.keys()))


class DictStorage(UserDict, BaseStorage):
    """A basic dict wrapper class for non-persistent, in-memory storage

    .. note::
        This is mostly a placeholder for when no other backends are available. For in-memory
        caching, either :py:class:`.SQLiteCache` (with `use_memory=True`) or :py:class:`.RedisCache`
        is recommended instead.

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._serializer = None

    def __getitem__(self, key):
        """An additional step is needed here for response data. Since the original response object
        is still in memory, its content has already been read and needs to be reset.
        """
        item = super().__getitem__(key)
        if getattr(item, 'raw', None):
            item.raw.reset()
        return item
