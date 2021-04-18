import pickle
import warnings
from abc import ABC
from collections.abc import MutableMapping
from logging import getLogger
from typing import Iterable, List, Tuple, Union

import requests
from requests.models import PreparedRequest

from ..cache_keys import create_key, url_to_key
from ..response import AnyResponse, CachedResponse, ExpirationTime

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
        self.redirects = {}
        self.responses = {}
        self.include_get_headers = include_get_headers
        self.ignored_parameters = ignored_parameters

    @property
    def urls(self) -> List[str]:
        """Get all URLs currently in the cache (excluding redirects)"""
        return [r.url for _, r in self._get_valid_responses()]

    def save_response(self, key: str, response: AnyResponse, expire_after: ExpirationTime = None):
        """Save response to cache

        Args:
            key: key for this response
            response: response to save
            expire_after: Time in seconds until this cache item should expire
        """
        self.responses[key] = CachedResponse(response, expire_after=expire_after)

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
            response.reset()  # In case response was in memory and raw content has already been read
            return response
        except KeyError:
            return default
        except (AttributeError, TypeError, ValueError, pickle.PickleError) as e:
            logger.error(f'Unable to deserialize response with key {key}: {str(e)}')
            return default

    def delete(self, key: str):
        """Delete `key` from cache. Also deletes all responses from response history"""
        self.delete_history(key)
        for cache in [self.responses, self.redirects]:
            # Skip `contains` checks to reduce # of service calls
            try:
                del cache[key]
            except (AttributeError, KeyError):
                pass

    def delete_history(self, key: str):
        """Delete redirect history associated with a response, if any"""
        try:
            response = self.responses[key] or self.responses[self.redirects[key]]
            for r in response.history:
                del self.redirects[create_key(r.request, self.ignored_parameters)]
        except Exception:
            pass

    def delete_url(self, url: str):
        """Delete response + redirects associated with `url` from cache.
        Works only for GET requests.
        """
        self.delete(url_to_key(url, self.ignored_parameters))

    def clear(self):
        """Delete all items from the cache"""
        logger.info('Clearing all items from the cache')
        self.responses.clear()
        self.redirects.clear()

    def remove_expired_responses(self, expire_after: ExpirationTime = None):
        """Remove expired responses from the cache, optionally with revalidation

        Args:
            expire_after: A new expiration time used to revalidate the cache
        """
        logger.info('Removing expired responses.' + (f'Revalidating with: {expire_after}' if expire_after else ''))
        for key, response in self._get_valid_responses():
            # If we're revalidating and it's not yet expired, update the cached item's expiration
            if expire_after is not None and not response.revalidate(expire_after):
                self.responses[key] = response
            if response.is_expired:
                self.delete(key)

    def remove_old_entries(self, *args, **kwargs):
        msg = 'BaseCache.remove_old_entries() is deprecated; ' 'please use CachedSession.remove_expired_responses()'
        warnings.warn(DeprecationWarning(msg))
        self.remove_expired_responses(*args, **kwargs)

    def _get_valid_responses(self) -> Iterable[Tuple[str, CachedResponse]]:
        """Get all responses from the cache, and delete any invalid ones"""
        for key in list(self.responses.keys()):
            # If a response is invalid, delete it
            try:
                yield key, self.responses[key]
            except Exception as e:
                logger.debug(f'Unable to deserialize response with key {key}: {str(e)}')
                self.delete(key)
                continue

    def create_key(self, request: requests.PreparedRequest, **kwargs) -> str:
        """Create a normalized cache key from a request object"""
        return create_key(request, self.ignored_parameters, self.include_get_headers, **kwargs)

    def has_key(self, key: str) -> bool:
        """Returns `True` if cache has `key`, `False` otherwise"""
        return key in self.responses or key in self.redirects

    def has_url(self, url: str) -> bool:
        """Returns `True` if cache has `url`, `False` otherwise. Works only for GET request urls"""
        return self.has_key(url_to_key(url, self.ignored_parameters))  # noqa: W601

    def __str__(self):
        return f'redirects: {len(self.redirects)}\nresponses: {len(self.responses)}'


class BaseStorage(MutableMapping, ABC):
    """Base class for backend storage implementations

    Args:
        secret_key: Optional secret key used to sign cache items for added security
        salt: Optional salt used to sign cache items
        suppress_warnings: Don't show a warning when not using ``secret_key``
        serializer: Custom serializer that provides ``loads`` and ``dumps`` methods
    """

    def __init__(
        self,
        secret_key: Union[Iterable, str, bytes] = None,
        salt: Union[str, bytes] = b'requests-cache',
        suppress_warnings: bool = False,
        serializer=None,
        **kwargs,
    ):
        self._serializer = serializer or self._get_serializer(secret_key, salt)
        logger.debug(f'Initializing {type(self).__name__} with serializer: {self._serializer}')

        # Show a warning instead of an exception if there are remaining unused kwargs
        if kwargs:
            logger.warning(f'Unrecognized keyword arguments: {kwargs}')
        if not secret_key:
            warn_func = logger.debug if suppress_warnings else warnings.warn
            warn_func('Using a secret key to sign cached items is recommended for this backend')

    def serialize(self, item: ResponseOrKey) -> bytes:
        """Serialize a URL or response into bytes"""
        return self._serializer.dumps(item)

    def deserialize(self, item: Union[ResponseOrKey, bytes]) -> ResponseOrKey:
        """Deserialize a cached URL or response"""
        return self._serializer.loads(bytes(item))

    @staticmethod
    def _get_serializer(secret_key, salt):
        """Get the appropriate serializer to use; either ``itsdangerous``, if a secret key is
        specified, or plain ``pickle`` otherwise.
        """
        # Import in function scope to make itsdangerous an optional dependency
        if secret_key:
            from itsdangerous.serializer import Serializer

            return Serializer(secret_key, salt=salt, serializer=pickle)
        else:
            return pickle
