"""Utilities for patching ``requests``. See :ref:`patching` for general usage info.

.. warning:: These functions are not thread-safe. Use :py:class:`.CachedSession` if you want to use
    caching in a multi-threaded environment.

.. automodsumm:: requests_cache.patcher
   :functions-only:
   :nosignatures:
"""
import inspect
from contextlib import contextmanager
from logging import getLogger
from typing import TYPE_CHECKING, List, Optional, Type
from warnings import warn

import requests

from .backends import BackendSpecifier, BaseCache, init_backend
from .session import CachedSession, OriginalSession

logger = getLogger(__name__)

if TYPE_CHECKING:
    MIXIN_BASE = CachedSession
else:
    MIXIN_BASE = object


class ModuleCacheMixin(MIXIN_BASE):
    """Session mixin that optionally caches requests only if sent from specific modules"""

    def __init__(
        self, *args, module_only: bool = False, modules: Optional[List[str]] = None, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.modules = modules or []
        self.module_only = module_only

    def request(self, *args, **kwargs):
        if self._is_module_enabled():
            return super().request(*args, **kwargs)
        else:
            return OriginalSession.request(self, *args, **kwargs)

    def _is_module_enabled(self) -> bool:
        if not self.module_only:
            return True
        return _calling_module(back=3) in self.modules

    def enable_module(self):
        self.modules.append(_calling_module())

    def disable_module(self):
        try:
            self.modules.remove(_calling_module())
        except ValueError:
            pass


def _calling_module(back: int = 2) -> str:
    """Get the name of the module ``back`` frames up in the call stack"""
    frame = inspect.stack()[back].frame
    module = inspect.getmodule(frame)
    return getattr(module, '__name__', '')


def install_cache(
    cache_name: str = 'http_cache',
    backend: Optional[BackendSpecifier] = None,
    module_only: bool = False,
    session_factory: Type[OriginalSession] = CachedSession,
    **kwargs,
):
    """
    Install the cache for all ``requests`` functions by monkey-patching :py:class:`requests.Session`

    Example:

        >>> requests_cache.install_cache('demo_cache')

    Accepts all parameters for :py:class:`.CachedSession`. Additional parameters:

    Args:
        module_only: Only install the cache for the current module
        session_factory: Session class to use. It must inherit from either
            :py:class:`.CachedSession` or :py:class:`.CacheMixin`
    """
    backend = init_backend(cache_name, backend, **kwargs)
    module = _calling_module()

    class _ConfiguredCachedSession(ModuleCacheMixin, session_factory):  # type: ignore  # See mypy issue #5865
        def __init__(self):
            super().__init__(
                cache_name=cache_name,
                backend=backend,
                module_only=module_only,
                modules=[module],
                **kwargs,
            )

    _patch_session_factory(_ConfiguredCachedSession)


def uninstall_cache(module_only: bool = False):
    """Disable the cache by restoring the original :py:class:`requests.Session`"""
    _patch_session_factory(OriginalSession)


@contextmanager
def disabled():
    """
    Context manager for temporarily disabling caching for all ``requests`` functions

    Example:

        >>> with requests_cache.disabled():
        ...     requests.get('https://httpbin.org/get')

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
    Context manager for temporarily enabling caching for all ``requests`` functions

    Example:

        >>> with requests_cache.enabled('cache.db'):
        ...     requests.get('https://httpbin.org/get')

    Accepts the same arguments as :py:class:`.CachedSession` and :py:func:`.install_cache`.
    """
    install_cache(*args, **kwargs)
    try:
        yield
    finally:
        uninstall_cache()


def get_cache() -> Optional[BaseCache]:
    """Get the internal cache object from the currently installed ``CachedSession`` (if any)"""
    return getattr(requests.Session(), 'cache', None)


def get_installed_modules() -> List[str]:
    """Get all modules that have caching installed"""
    session = requests.Session()
    if isinstance(session, ModuleCacheMixin):
        return session.modules
    else:
        return []


def is_installed() -> bool:
    """Indicate whether or not requests-cache is currently installed"""
    return isinstance(requests.Session(), CachedSession)


def clear():
    """Clear the currently installed cache (if any)"""
    if get_cache():
        get_cache().clear()


def delete(*args, **kwargs):
    """Remove responses from the cache according one or more conditions.
    See :py:meth:`.BaseCache.delete for usage details.
    """
    session = requests.Session()
    if isinstance(session, CachedSession):
        session.cache.delete(*args, **kwargs)


def remove_expired_responses():
    """Remove expired responses from the cache"""
    warn(
        'remove_expired_responses() is deprecated; please use delete() instead',
        DeprecationWarning,
    )
    delete(expired=True)


def _patch_session_factory(session_factory: Type[OriginalSession] = CachedSession):
    logger.debug(f'Patching requests.Session with class: {session_factory.__name__}')
    requests.Session = requests.sessions.Session = session_factory  # type: ignore
