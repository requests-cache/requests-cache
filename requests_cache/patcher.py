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

# TODO: This is going to require thinking through many more edge cases.
#   Lots of ways this could potentially go wrong.
# TODO: What if we want to use module_only but patch an external library? Options:
#   1. Check if enabled module is anywhere in the call stack (e.g., it called some other module that
#      made the request)
#   2. Provide target module to patch (e.g., 'github.Requester')

logger = getLogger(__name__)

if TYPE_CHECKING:
    MIXIN_BASE = CachedSession
else:
    MIXIN_BASE = object


def install_cache(
    cache_name: str = 'http_cache',
    backend: Optional[BackendSpecifier] = None,
    module_only: bool = False,
    session: CachedSession = None,
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
        session: An existing session object to use
        session_factory: Session class to use. It must inherit from either
            :py:class:`.CachedSession` or :py:class:`.CacheMixin`
    """
    # Patch with an existing session object
    if session:
        cls = _get_session_wrapper(session)
        _patch_session_factory(cls)
    # Patch only for the current module
    elif module_only:
        if not is_installed:
            session = ModuleCachedSession(
                cache_name=cache_name,
                backend=init_backend(cache_name, backend, **kwargs),
                **kwargs,
            )
            cls = _get_session_wrapper(session)
            _patch_session_factory(cls)
        requests.Session._session.enable_module()

        # modules = get_installed_modules() + [_calling_module()]
        # _enable_module(
        #     cache_name,
        #     init_backend(cache_name, backend, **kwargs),
        #     modules,
        #     **kwargs,
        # )
        # cls = _get_configured_session(
        #     ModuleCachedSession,
        #     cache_name=cache_name,
        #     backend=backend,
        #     include_modules=modules,
        #     **kwargs,
        # )
        # _patch_session_factory(cls)
    # Patch with CachedSession or session_factory
    else:
        cls = _get_configured_session(
            session_factory,
            cache_name=cache_name,
            backend=init_backend(cache_name, backend, **kwargs),
            **kwargs,
        )
        _patch_session_factory(cls)


def uninstall_cache(module_only: bool = False):
    """Disable the cache by restoring the original :py:class:`requests.Session`

    Args:
        module_only: Only uninstall the cache for the current module
    """
    if not is_installed():
        return
    elif module_only:
        requests.Session._session.disable_module()
    else:
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
    if isinstance(session, ModuleCachedSession):
        return list(session.include_modules)
    else:
        return []


def is_installed() -> bool:
    """Indicate whether or not requests-cache is currently installed"""
    session = requests.Session()
    if isinstance(session, ModuleCachedSession):
        return session.is_module_enabled()
    else:
        return isinstance(session, CachedSession)


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


class ModuleCachedSession(CachedSession):
    """Session mixin that only caches requests sent from specific modules. May be used in one of two
    modes:

    * Opt-in: caching is disabled by default, and enabled for modules in ``include_modules``
    * Opt-out: caching is enabled by default, and disabled for modules in ``exclude_modules``

    Args:
        include_modules: List of modules to enable caching for
        exclude_modules: List of modules to disable caching for
        opt_in: Whether to use opt-in mode (``True``) or opt-out mode (``False``)
    """

    def __init__(
        self,
        *args,
        include_modules: List[str] = None,
        exclude_modules: List[str] = None,
        opt_in: bool = True,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.include_modules = set(include_modules or [])
        self.exclude_modules = set(exclude_modules or [])
        self.opt_in = opt_in

    def close(self):
        """Only close adapter(s) and skip closing backend connections in CachedSession.close(), as
        the object may be reused after closing. :py:func:`requests.request` will create a session
        for the request and close it after use. We will keep this behavior to avoid memory leaks.
        Adapter(s) will create new connections if re-used after closing.
        """
        for v in self.adapters.values():
            v.close()

    def disable_module(self):
        module = _calling_module()
        if self.opt_in:
            self.include_modules -= {module}
        else:
            self.exclude_modules |= {module}
        logger.info(f'Caching disabled for {module}')

    def enable_module(self):
        module = _calling_module()
        if self.opt_in:
            self.include_modules |= {module}
        else:
            self.exclude_modules -= {module}
        logger.info(f'Caching enabled for {module}')

    def is_module_enabled(self, back: int = 2) -> bool:
        module = _calling_module(back=back)
        if self.opt_in:
            return module in self.include_modules
        else:
            return module not in self.exclude_modules

    def request(self, *args, **kwargs):
        if self.is_module_enabled(back=3):
            return super().request(*args, **kwargs)
        else:
            return OriginalSession.request(self, *args, **kwargs)


def _calling_module(back: int = 2) -> str:
    """Get the name of the module ``back`` frames up in the call stack"""
    frame = inspect.stack()[back].frame
    module = inspect.getmodule(frame)
    return getattr(module, '__name__', '')


# testing
def _calling_module_2() -> str:
    """Get the name of the calling module (first module outside of requests-cache)"""
    for module in _stack_modules():
        if not module.startswith('requests_cache'):
            return module

    raise RuntimeError('Could not determine calling module')


def _stack_modules() -> Iterator[str]:
    for frame_info in inspect.stack():
        module = inspect.getmodule(frame_info.frame)
        yield getattr(module, '__name__', '')


# def _enable_module(
#     cache_name: str,
#     backend: BackendSpecifier,
#     modules: List[str],
#     **kwargs,
# ):
#     """Install the cache for specific modules"""
#     if not is_installed():
#         return

#     requests.Session._session.enable_module()

#     class _ConfiguredCachedSession(ModuleCachedSession):  # type: ignore  # See mypy issue #5865
#         def __init__(self):
#             super().__init__(
#                 cache_name=cache_name, backend=backend, include_modules=modules, **kwargs
#             )

#     _patch_session_factory(_ConfiguredCachedSession)


# def _disable_module():
#     """Uninstall the cache for the current module"""
#     session = requests.Session()
#     if not isinstance(session, ModuleCachedSession):
#         return

#     modules = get_installed_modules()
#     modules.remove(_calling_module())

#     # No enabled modules remaining; restore the original Session
#     if not modules:
#         uninstall_cache()
#     # Reinstall cache with updated modules
#     else:
#         _enable_module(
#             session.cache.cache_name,
#             session.cache,
#             CachedSession,
#             modules,
#             **session.settings.to_dict(),
#         )


def _get_configured_session(
    session_factory: Type[OriginalSession], *args, **kwargs
) -> Type[OriginalSession]:
    class _ConfiguredCachedSession(session_factory):  # type: ignore  # See mypy issue #5865
        def __init__(self):
            super().__init__(*args, **kwargs)

    return _ConfiguredCachedSession


def _get_session_wrapper(session: CachedSession):
    """Create a wrapper Session class that returns an existing session object when created"""

    class _SessionWrapper(OriginalSession):
        """Wrapper for an existing session object, as a mutable class attribute"""

        _session = session

        def __new__(cls, *args, **kwargs):
            return cls._session

    return _SessionWrapper


def _patch_session_factory(session_factory: Type[OriginalSession]):
    logger.debug(f'Patching requests.Session with class: {session_factory.__name__}')
    requests.Session = requests.sessions.Session = session_factory  # type: ignore
