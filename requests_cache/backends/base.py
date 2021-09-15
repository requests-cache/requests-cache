import pickle
import warnings
from abc import ABC
from collections import UserDict
from collections.abc import MutableMapping
from datetime import datetime
from logging import getLogger
from typing import Iterable, Iterator, Tuple, Union

from ..cache_control import ExpirationTime
from ..cache_keys import create_key, remove_ignored_params, remove_ignored_url_params, url_to_key
from ..models import AnyRequest, AnyResponse, CachedResponse
from ..serializers import init_serializer

# Specific exceptions that may be raised during deserialization
DESERIALIZE_ERRORS = (AttributeError, ImportError, TypeError, ValueError, pickle.PickleError)

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
        self.name: str = kwargs.get('cache_name', '')
        self.redirects: BaseStorage = DictStorage()
        self.responses: BaseStorage = DictStorage()
        self.include_get_headers = include_get_headers or kwargs.get('match_headers', False)
        self.ignored_parameters = ignored_parameters

    @property
    def urls(self) -> Iterator[str]:
        """Get all URLs currently in the cache (excluding redirects)"""
        for response in self.values():
            yield response.url

    def save_response(self, response: AnyResponse, cache_key: str = None, expires: datetime = None):
        """Save response to cache

        Args:
            cache_key: Cache key for this response; will otherwise be generated based on request
            response: response to save
            expire_after: Time in seconds until this cache item should expire
        """
        cache_key = cache_key or self.create_key(response.request)
        cached_response = CachedResponse.from_response(response, cache_key=cache_key, expires=expires)
        cached_response.request = remove_ignored_params(cached_response.request, self.ignored_parameters)
        cached_response.url = remove_ignored_url_params(cached_response.url, self.ignored_parameters)
        self.responses[cache_key] = cached_response

    def save_redirect(self, request: AnyRequest, response_key: str):
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

    def delete_urls(self, urls: Iterable[str]):
        """Delete cached responses + redirects for multiple request URLs (``GET`` requests only)"""
        self.bulk_delete([url_to_key(url, self.ignored_parameters) for url in urls])

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

        for key, response in self._get_valid_responses(delete=True):
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

    def create_key(self, request: AnyRequest, **kwargs) -> str:
        """Create a normalized cache key from a request object"""
        return create_key(request, self.ignored_parameters, self.include_get_headers, **kwargs)  # type: ignore

    def has_key(self, key: str) -> bool:
        """Returns `True` if cache has `key`, `False` otherwise"""
        return key in self.responses or key in self.redirects

    def has_url(self, url: str) -> bool:
        """Returns `True` if cache has `url`, `False` otherwise. Works only for GET request urls"""
        return self.has_key(url_to_key(url, self.ignored_parameters))  # noqa: W601

    def keys(self, check_expiry=False) -> Iterator[str]:
        """Get all cache keys for redirects and valid responses combined"""
        yield from self.redirects.keys()
        for key, _ in self._get_valid_responses(check_expiry=check_expiry):
            yield key

    def values(self, check_expiry=False) -> Iterator[CachedResponse]:
        """Get all valid response objects from the cache"""
        for _, response in self._get_valid_responses(check_expiry=check_expiry):
            yield response

    def response_count(self, check_expiry=False) -> int:
        """Get the number of responses in the cache, excluding invalid (unusable) responses.
        Can also optionally exclude expired responses.
        """
        return len(list(self.values(check_expiry=check_expiry)))

    def _get_valid_responses(
        self, check_expiry=False, delete=False
    ) -> Iterator[Tuple[str, CachedResponse]]:
        """Get all responses from the cache, and skip (+ optionally delete) any invalid ones that
        can't be deserialized. Can also optionally check response expiry and exclude expired responses.
        """
        invalid_keys = []

        for key in self.responses.keys():
            try:
                response = self.responses[key]
                if check_expiry and response.is_expired:
                    invalid_keys.append(key)
                else:
                    yield key, response
            except DESERIALIZE_ERRORS:
                invalid_keys.append(key)

        # Delay deletion until the end, to improve responsiveness when used as a generator
        if delete:
            logger.debug(f'Deleting {len(invalid_keys)} invalid/expired responses')
            self.bulk_delete(invalid_keys)

    def __str__(self):
        """Show a count of total **rows** currently stored in the backend. For performance reasons,
        this does not check for invalid or expired responses.
        """
        return f'Total rows: {len(self.responses)} responses, {len(self.redirects)} redirects'

    def __repr__(self):
        return f'<{self.__class__.__name__}(name={self.name})>'


class BaseStorage(MutableMapping, ABC):
    """Base class for backend storage implementations

    Args:
        secret_key: Optional secret key used to sign cache items for added security
        salt: Optional salt used to sign cache items
        serializer: Custom serializer that provides ``loads`` and ``dumps`` methods
    """

    def __init__(
        self,
        serializer=None,
        **kwargs,
    ):
        self.serializer = init_serializer(serializer, **kwargs)
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


class DictStorage(UserDict, BaseStorage):
    """A basic dict wrapper class for non-persistent storage"""
