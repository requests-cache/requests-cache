"""Functions for monkey-patching ``requests``"""
from contextlib import contextmanager
from logging import getLogger
from typing import Callable, Dict, Iterable, Optional, Type

import requests

from .backends import BackendSpecifier, BaseCache
from .response import ExpirationTime
from .session import CachedSession, OriginalSession

logger = getLogger(__name__)


def install_cache(
    cache_name: str = 'http-cache',
    backend: BackendSpecifier = None,
    expire_after: ExpirationTime = -1,
    urls_expire_after: Dict[str, ExpirationTime] = None,
    allowable_codes: Iterable[int] = (200,),
    allowable_methods: Iterable['str'] = ('GET', 'HEAD'),
    filter_fn: Callable = None,
    old_data_on_error: bool = False,
    session_factory: Type[OriginalSession] = CachedSession,
    **kwargs,
):
    """
    Installs cache for all ``requests`` functions by monkey-patching ``Session``

    Parameters are the same as in :py:class:`.CachedSession`. Additional parameters:

    Args:
        session_factory: Session class to use. It must inherit from either
            :py:class:`.CachedSession` or :py:class:`.CacheMixin`
    """

    class _ConfiguredCachedSession(session_factory):
        def __init__(self):
            super().__init__(
                cache_name=cache_name,
                backend=backend,
                expire_after=expire_after,
                urls_expire_after=urls_expire_after,
                allowable_codes=allowable_codes,
                allowable_methods=allowable_methods,
                filter_fn=filter_fn,
                old_data_on_error=old_data_on_error,
                **kwargs,
            )

    _patch_session_factory(_ConfiguredCachedSession)


def uninstall_cache():
    """Restores ``requests.Session`` and disables cache"""
    _patch_session_factory(OriginalSession)


@contextmanager
def disabled():
    """
    Context manager for temporary disabling globally installed cache

    .. warning:: not thread-safe

    ::

        >>> with requests_cache.disabled():
        ...     requests.get('http://httpbin.org/ip')
        ...     requests.get('http://httpbin.org/get')

    """
    previous = requests.Session
    uninstall_cache()
    try:
        yield
    finally:
        _patch_session_factory(previous)


@contextmanager
def enabled(*args, **kwargs):
    """
    Context manager for temporary installing global cache.

    Accepts same arguments as :func:`install_cache`

    .. warning:: not thread-safe

    ::

        >>> with requests_cache.enabled('cache_db'):
        ...     requests.get('http://httpbin.org/get')

    """
    install_cache(*args, **kwargs)
    try:
        yield
    finally:
        uninstall_cache()


def get_cache() -> Optional[BaseCache]:
    """Returns internal cache object from globally installed ``CachedSession``"""
    return requests.Session().cache if is_installed() else None


def is_installed():
    """Indicate whether or not requests-cache is installed"""
    return isinstance(requests.Session(), CachedSession)


def clear():
    """Clears globally installed cache"""
    if get_cache():
        get_cache().clear()


def remove_expired_responses(expire_after: ExpirationTime = None):
    """Remove expired responses from the cache, optionally with revalidation

    Args:
        expire_after: A new expiration time used to revalidate the cache
    """
    if is_installed():
        return requests.Session().remove_expired_responses(expire_after)


def _patch_session_factory(session_factory: Type[OriginalSession] = CachedSession):
    logger.info(f'Patching requests.Session with class: {type(session_factory).__name__}')
    requests.Session = requests.sessions.Session = session_factory  # noqa
