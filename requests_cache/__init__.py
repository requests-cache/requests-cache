# flake8: noqa: E402,F401
from logging import getLogger
from os import getenv

__version__ = '0.7.0'

logger = getLogger(__name__)


try:
    from .backends import *
    from .patcher import *
    from .response import CachedHTTPResponse, CachedResponse
    from .session import ALL_METHODS, CachedSession, CacheMixin
# Log and ignore ImportErrors, if setup.py is invoked outside a virtualenv
except ImportError as e:
    logger.warning(e)
