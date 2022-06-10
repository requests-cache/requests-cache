"""Base classes for all cache backends

.. automodsumm:: requests_cache.backends.base
   :classes-only:
   :nosignatures:
"""
from __future__ import annotations

from abc import ABC
from collections import UserDict
from collections.abc import MutableMapping
from datetime import datetime
from logging import getLogger
from pickle import PickleError
from typing import TYPE_CHECKING, Iterable, Iterator, Optional, Tuple

from requests import PreparedRequest, Response

from requests_cache.serializers.cattrs import CattrStage
from requests_cache.serializers.pipeline import SerializerPipeline

from ..cache_keys import create_key, redact_response
from ..models import CachedResponse
from ..policy import DEFAULT_CACHE_NAME, CacheSettings, ExpirationTime
from ..serializers import SERIALIZERS, SerializerType, pickle_serializer

# Specific exceptions that may be raised during deserialization
DESERIALIZE_ERRORS = (AttributeError, ImportError, PickleError, TypeError, ValueError)

logger = getLogger(__name__)


class BaseCache:
    """Base class for cache backends. Can be used as a non-persistent, in-memory cache.

    This manages higher-level cache operations, including:

    * Saving and retrieving responses
    * Managing redirect history
    * Convenience methods for general cache info

    Lower-level storage operations are handled by :py:class:`.BaseStorage`.

    To extend this with your own custom backend, see :ref:`custom-backends`.

    Args:
        cache_name: Cache prefix or namespace, depending on backend
        serializer: Serializer name or instance
        kwargs: Additional backend-specific keyword arguments
    """

    def __init__(self, cache_name: str = DEFAULT_CACHE_NAME, **kwargs):
        self.cache_name = cache_name
        self.responses: BaseStorage = DictStorage()
        self.redirects: BaseStorage = DictStorage()
        self._settings = CacheSettings()  # Init and public access is done in CachedSession

    @property
    def urls(self) -> Iterator[str]:
        """Get all URLs currently in the cache (excluding redirects)"""
        for response in self.values():
            yield response.url

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

    def save_response(self, response: Response, cache_key: str = None, expires: datetime = None):
        """Save a response to the cache

        Args:
            cache_key: Cache key for this response; will otherwise be generated based on request
            response: Response to save
            expires: Absolute expiration time for this response
        """
        cache_key = cache_key or self.create_key(response.request)
        cached_response = CachedResponse.from_response(response, expires=expires)
        cached_response = redact_response(cached_response, self._settings.ignored_parameters)
        self.responses[cache_key] = cached_response
        for r in response.history:
            self.redirects[self.create_key(r.request)] = cache_key

    def clear(self):
        """Delete all items from the cache"""
        logger.info('Clearing all items from the cache')
        self.responses.clear()
        self.redirects.clear()

    def close(self):
        """Close any open backend connections"""
        logger.debug('Closing backend connections')
        self.responses.close()
        self.redirects.close()

    def create_key(self, request: PreparedRequest = None, **kwargs) -> str:
        """Create a normalized cache key from a request object"""
        key_fn = self._settings.key_fn or create_key
        return key_fn(
            request=request,
            ignored_parameters=self._settings.ignored_parameters,
            match_headers=self._settings.match_headers,
            serializer=self.responses.serializer,
            **kwargs,
        )

    def delete(self, key: str):
        """Delete a response or redirect from the cache, as well any associated redirect history"""
        # If it's a response key, first delete any associated redirect history
        try:
            for r in self.responses[key].history:
                del self.redirects[create_key(r.request, self._settings.ignored_parameters)]
        except (KeyError, *DESERIALIZE_ERRORS):
            pass
        # Then delete the response itself, or just the redirect if it's a redirect key
        for cache in [self.responses, self.redirects]:
            try:
                del cache[key]
            except KeyError:
                pass

    def delete_url(self, url: str, method: str = 'GET', **kwargs):
        """Delete a cached response for the specified request"""
        key = self.create_key(method=method, url=url, **kwargs)
        self.delete(key)

    def delete_urls(self, urls: Iterable[str], method: str = 'GET', **kwargs):
        """Delete all cached responses for the specified requests"""
        keys = [self.create_key(method=method, url=url, **kwargs) for url in urls]
        self.bulk_delete(keys)

    def bulk_delete(self, keys: Iterable[str]):
        """Remove multiple responses and their associated redirects from the cache"""
        self.responses.bulk_delete(keys)
        self.remove_invalid_redirects()

    def has_key(self, key: str) -> bool:
        """Returns ``True`` if ``key`` is in the cache"""
        return key in self.responses or key in self.redirects

    def has_url(self, url: str, method: str = 'GET', **kwargs) -> bool:
        """Returns ``True`` if the specified request is cached"""
        key = self.create_key(method=method, url=url, **kwargs)
        return self.has_key(key)  # noqa: W601

    def keys(self, include_expired: bool = True) -> Iterator[str]:
        """Get all cache keys for redirects and responses combined"""
        yield from self.redirects.keys()
        for key, _ in self.items(include_expired=include_expired):
            yield key

    def values(self, include_expired: bool = True) -> Iterator[CachedResponse]:
        """Get all response objects from the cache"""
        for _, response in self.items(include_expired=include_expired):
            if TYPE_CHECKING:
                assert response is not None
            yield response

    def items(
        self, include_expired: bool = True, include_invalid: bool = False
    ) -> Iterator[Tuple[str, Optional[CachedResponse]]]:
        """Get all keys and responses from the cache, and optionally skip any expired or invalid
        ones

        Args:
            include_expired: Include expired responses in the results
            include_invalid: Include invalid responses in the results
        """
        for key in self.responses.keys():
            try:
                response = self.responses[key]
                response.cache_key = key
                if include_expired or not response.is_expired:
                    yield key, response
            except DESERIALIZE_ERRORS:
                if include_invalid:
                    yield key, None

    def remove(
        self, expired: bool = False, invalid: bool = True, older_than: ExpirationTime = None
    ):
        """Remove responses from the cache according to the specified condition(s).

        Args:
            expired: Remove all expired responses
            invalid: Remove all invalid responses (ones that can't be deserialized with current
                settings)
            older_than: Remove all cache items older than this value, **relative to the cache
                creation time**
        """
        if expired:
            logger.info('Removing expired responses')
        if older_than:
            logger.info(f'Removing responses older than {older_than}')
        keys_to_delete = []

        for key, response in self.items(include_invalid=invalid):
            if (
                response is None  # If the response was invalid
                or (expired and response.is_expired)
                or (older_than is not None and response.is_older_than(older_than))
            ):
                keys_to_delete.append(key)

        # Delay deletes until the end, to use more efficient bulk_delete
        logger.debug(f'Deleting {len(keys_to_delete)} expired responses')
        self.bulk_delete(keys_to_delete)

    def remove_expired_responses(self, expire_after: ExpirationTime = None):
        """Remove expired and invalid responses from the cache

        **Deprecated:** Please use :py:meth:`.remove` with ``expire=True`` instead.
        """
        self.remove(expired=True, invalid=True)
        if expire_after:
            self.reset_expiration(expire_after)

    def remove_invalid_redirects(self):
        """Remove any redirects that no longer point to an existing response"""
        invalid_redirects = [k for k, v in self.redirects.items() if v not in self.responses]
        self.redirects.bulk_delete(invalid_redirects)

    def reset_expiration(self, expire_after: ExpirationTime = None):
        """Set a new expiration value to set on existing cache items

        Args:
            expire_after: New expiration value, **relative to the current time**
        """
        logger.info(f'Resetting expiration with: {expire_after}')
        for key, response in self.items():
            if TYPE_CHECKING:
                assert response is not None
            response.reset_expiration(expire_after)
            self.responses[key] = response

    def response_count(self, include_expired: bool = True) -> int:
        """Get the number of responses in the cache, excluding invalid responses.
        Can also optionally exclude expired responses.
        """
        return len(list(self.values(include_expired=include_expired)))

    def update(self, other: 'BaseCache'):
        """Update this cache with the contents of another cache"""
        logger.debug(f'Copying {len(other.responses)} responses from {repr(other)} to {repr(self)}')
        self.responses.update(other.responses)
        self.redirects.update(other.redirects)

    def __str__(self):
        """Show a count of total **rows** currently stored in the backend. For performance reasons,
        this does not check for invalid or expired responses.
        """
        return f'<{self.__class__.__name__}(name={self.cache_name})>'

    def __repr__(self):
        return str(self)


class BaseStorage(MutableMapping, ABC):
    """Base class for client-agnostic storage implementations. Notes:

    * This provides a common dictionary-like interface for the underlying storage operations
      (create, read, update, delete).
    * One ``BaseStorage`` instance corresponds to a single table/hash/collection, or whatever the
      backend-specific equivalent may be.
    * ``BaseStorage`` subclasses contain no behavior specific to ``requests``, which are handled by
      :py:class:`.BaseCache` subclasses.
    * ``BaseStorage`` also contains a serializer object (defaulting to :py:mod:`pickle`), which
      determines how :py:class:`.CachedResponse` objects are saved internally. See :ref:`serializers`
      for details.

    Args:
        serializer: Custom serializer that provides ``loads`` and ``dumps`` methods
        no_serializer: Explicitly disable serialization, and write values as-is; this is to avoid
            ambiguity with ``serializer=None``
        decode_content: Decode JSON or text response body into a human-readable format
        kwargs: Additional backend-specific keyword arguments
    """

    # Default serializer to use for responses, if one isn't specified; may be overridden by subclass
    default_serializer: SerializerType = pickle_serializer

    def __init__(
        self,
        serializer: SerializerType = None,
        no_serializer: bool = False,
        decode_content: bool = False,
        **kwargs,
    ):
        # Set a default serializer, unless explicitly disabled
        self.serializer = None if no_serializer else (serializer or self.default_serializer)

        # Look up a serializer by name, if needed
        if isinstance(self.serializer, str):
            self.serializer = SERIALIZERS[self.serializer]
        if isinstance(self.serializer, (SerializerPipeline, CattrStage)):
            self.serializer.decode_content = decode_content
        logger.debug(f'Initialized {type(self).__name__} with serializer: {self.serializer}')

    def bulk_delete(self, keys: Iterable[str]):
        """Delete multiple keys from the cache, without raising errors for missing keys. This is a
        naive, generic implementation that subclasses should override with a more efficient
        backend-specific implementation, if possible.
        """
        for k in keys:
            try:
                del self[k]
            except KeyError:
                pass

    def close(self):
        """Close any open backend connections"""

    def serialize(self, value):
        """Serialize value, if a serializer is available"""
        return self.serializer.dumps(value) if self.serializer else value

    def deserialize(self, value):
        """Deserialize value, if a serializer is available"""
        return self.serializer.loads(value) if self.serializer else value

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
        self.serializer = None

    def __getitem__(self, key):
        """An additional step is needed here for response data. The original response object
        is still in memory, and hasn't gone through a serialize/deserialize loop. So, the file-like
        response body has already been read, and needs to be reset.
        """
        item = super().__getitem__(key)
        if getattr(item, 'raw', None):
            item.raw.reset()
        return item
