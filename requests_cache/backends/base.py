import pickle
import warnings
from abc import ABC
from collections.abc import MutableMapping
from datetime import datetime
from logging import getLogger
from typing import Iterable, Iterator, Tuple, Union

import requests
from requests.models import PreparedRequest

from ..cache_control import ExpirationTime
from ..cache_keys import create_key, remove_ignored_params, url_to_key
from ..models.response import AnyResponse, CachedResponse
from ..serializers import SERIALIZERS

# Specific exceptions that may be raised during deserialization
DESERIALIZE_ERRORS = (AttributeError, TypeError, ValueError, pickle.PickleError)

ResponseOrKey = Union[CachedResponse, str]
logger = getLogger(__name__)


class BaseCache:
    """Base class for cache implementations, which can also be used as in-memory cache.

    See :ref:`advanced_usage:custom backends` for details on creating your own implementation.
    """

    def __init__(
        self,
        *args,
        include_get_headers: bool = False,
        ignored_parameters: Iterable[str] = None,
        **kwargs,
    ):
        self.name = None
        self.redirects = {}
        self.responses = {}
        self.include_get_headers = include_get_headers
        self.ignored_parameters = ignored_parameters

    @property
    def urls(self) -> Iterator[str]:
        """Get all URLs currently in the cache (excluding redirects)"""
        for response in self.values():
            yield response.url

    def save_response(self, response: AnyResponse, key: str = None, expires: datetime = None):
        """Save response to cache

        Args:
            key: key for this response
            response: response to save
            expire_after: Time in seconds until this cache item should expire
        """
        key = key or self.create_key(response.request)

        cached_response = CachedResponse.from_response(response, expires=expires)
        cached_response.request = remove_ignored_params(cached_response.request, self.ignored_parameters)
        self.responses[key] = cached_response

    def save_redirect(self, request: PreparedRequest, response_key: str):
        """
        Map a redirect request to a response. This makes it possible to associate many keys with a
        single response.

        Args:
            request: Request object for redirect URL
            response_key: Cache key which can be found in ``responses``
        """
        self.redirects[self.create_key(request)] = response_key

    def get_response(self, key: str, default=None) -> CachedResponse:
        """Retrieves response for `key` if it's stored in cache, otherwise returns `default`

        Args:
            key: Key of resource
            default: Value to return if `key` is not in cache
        """
        try:
            if key not in self.responses:
                key = self.redirects[key]
            response = self.responses[key]
            response.reset()  # In case response was in memory and content has already been read
            return response
        except KeyError:
            return default
        except DESERIALIZE_ERRORS as e:
            logger.error(f'Unable to deserialize response with key {key}: {str(e)}')
            logger.debug(e, exc_info=True)
            return default

    def delete(self, key: str):
        """Delete a response or redirect from the cache, as well any associated redirect history"""
        # If it's a response key, first delete any associated redirect history
        try:
            for r in self.responses[key].history:
                del self.redirects[create_key(r.request, self.ignored_parameters)]
        except (KeyError, *DESERIALIZE_ERRORS):
            pass
        # Then delete the response itself, or just the redirect if it's a redirect key
        for cache in [self.responses, self.redirects]:
            try:
                del cache[key]
            except KeyError:
                pass

    def delete_url(self, url: str):
        """Delete a cached response + redirects for ``GET <url>``"""
        self.delete(url_to_key(url, self.ignored_parameters))

    def bulk_delete(self, keys: Iterable[str]):
        """Remove multiple responses and their associated redirects from the cache"""
        self.responses.bulk_delete(keys)
        # Remove any redirects that no longer point to an existing response
        invalid_redirects = [k for k, v in self.redirects.items() if v not in self.responses]
        self.redirects.bulk_delete(set(keys + invalid_redirects))

    def clear(self):
        """Delete all items from the cache"""
        logger.info('Clearing all items from the cache')
        self.responses.clear()
        self.redirects.clear()

    def remove_expired_responses(self, expire_after: ExpirationTime = None):
        """Remove expired and invalid responses from the cache, optionally with revalidation

        Args:
            expire_after: A new expiration time used to revalidate the cache
        """
        logger.info(
            'Removing expired responses.'
            + (f'Revalidating with: {expire_after}' if expire_after else '')
        )
        keys_to_update = {}
        keys_to_delete = []

        for key, response in self._get_valid_responses(delete_invalid=True):
            # If we're revalidating and it's not yet expired, update the cached item's expiration
            if expire_after is not None and not response.revalidate(expire_after):
                keys_to_update[key] = response
            if response.is_expired:
                keys_to_delete.append(key)

        # Delay updates & deletes until the end, to avoid conflicts with _get_valid_responses()
        logger.debug(f'Deleting {len(keys_to_delete)} expired responses')
        self.bulk_delete(keys_to_delete)
        if expire_after is not None:
            logger.debug(f'Updating {len(keys_to_update)} revalidated responses')
            for key, response in keys_to_update.items():
                self.responses[key] = response

    def remove_old_entries(self, *args, **kwargs):
        msg = 'BaseCache.remove_old_entries() is deprecated; please use CachedSession.remove_expired_responses()'
        warnings.warn(DeprecationWarning(msg))
        self.remove_expired_responses(*args, **kwargs)

    def create_key(self, request: requests.PreparedRequest, **kwargs) -> str:
        """Create a normalized cache key from a request object"""
        return create_key(request, self.ignored_parameters, self.include_get_headers, **kwargs)

    def has_key(self, key: str) -> bool:
        """Returns `True` if cache has `key`, `False` otherwise"""
        return key in self.responses or key in self.redirects

    def has_url(self, url: str) -> bool:
        """Returns `True` if cache has `url`, `False` otherwise. Works only for GET request urls"""
        return self.has_key(url_to_key(url, self.ignored_parameters))  # noqa: W601

    def keys(self) -> Iterator[str]:
        """Get all cache keys for redirects and (valid) responses combined"""
        yield from self.redirects.keys()
        for key, _ in self._get_valid_responses():
            yield key

    def values(self) -> Iterator[CachedResponse]:
        """Get all valid response objects from the cache"""
        for _, response in self._get_valid_responses():
            yield response

    def _get_valid_responses(self, delete_invalid=False) -> Iterator[Tuple[str, CachedResponse]]:
        """Get all responses from the cache, and skip (+ optionally delete) any invalid ones that
        can't be deserialized"""
        keys_to_delete = []

        for key in self.responses.keys():
            try:
                yield key, self.responses[key]
            except DESERIALIZE_ERRORS:
                keys_to_delete.append(key)

        # Delay deletion until the end, to improve responsiveness when used as a generator
        if delete_invalid:
            logger.debug(f'Deleting {len(keys_to_delete)} invalid responses')
            self.bulk_delete(keys_to_delete)

    def __str__(self):
        return f'redirects: {len(self.redirects)}\nresponses: {len(self.responses)}'

    def __repr__(self):
        return f'<{self.__class__.__name__}(name={self.name})>'


class BaseStorage(MutableMapping, ABC):
    """Base class for backend storage implementations

    Args:
        secret_key: Optional secret key used to sign cache items for added security
        salt: Optional salt used to sign cache items
        suppress_warnings: Don't show a warning when not using ``secret_key``
        serializer: Custom serializer that provides ``loads`` and ``dumps`` methods
    """

    DEFAULT_SERIALIZER = 'pickle'

    def __init__(
        self,
        serializer=None,
        suppress_warnings: bool = False,
        **kwargs,
    ):
        serializer = serializer or self.DEFAULT_SERIALIZER

        if "secret_key" in kwargs and serializer == 'pickle':
            serializer = 'safe_pickle'

        if isinstance(serializer, str):
            self.serializer = SERIALIZERS[serializer]

        if callable(self.serializer):
            self.serializer = self.serializer(**kwargs)

        if not is_serializer(self.serializer):
            breakpoint()
            raise ValueError(
                f"Selected serializer {self.serializer} is not a serializer. Must have dumps/loads"
            )
        logger.debug(f'Initializing {type(self).__name__} with serializer: {self.serializer}')

    def bulk_delete(self, keys: Iterable[str]):
        """Delete multiple keys from the cache. Does not raise errors for missing keys. This is a
        basic version that subclasses should override with a more efficient backend-specific
        version, if possible.
        """
        for k in keys:
            try:
                del self[k]
            except KeyError:
                pass

    def __str__(self):
        return str(list(self.keys()))


def is_serializer(obj):
    # Checks if a proposed serializer has these three required attributes
    return hasattr(obj, 'dumps') and hasattr(obj, 'loads')
