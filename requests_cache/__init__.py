# flake8: noqa: E402,F401
from logging import getLogger
from os import getenv

__version__ = '0.7.0'
__version__ += getenv('PRE_RELEASE_SUFFIX', '')

logger = getLogger(__name__)


try:
    from .response import AnyResponse, CachedHTTPResponse, CachedResponse, ExpirationTime
    from .session import ALL_METHODS, CachedSession, CacheMixin
    from .patcher import (
        clear,
        disabled,
        enabled,
        get_cache,
        install_cache,
        is_installed,
        remove_expired_responses,
        uninstall_cache,
    )
# Ignore ImportErrors, if setup.py is invoked outside a virtualenv
except ImportError as e:
    logger.warning(e)
