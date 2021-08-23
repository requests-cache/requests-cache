# flake8: noqa: E402,F401
from logging import getLogger

logger = getLogger(__name__)

# Version is defined in pyproject.toml.
# It's copied here to make it easier for client code to check the installed version.
__version__ = '0.7.5'


def get_placeholder_class(original_exception: Exception = None):
    """Create a placeholder type for a class that does not have dependencies installed.
    This allows delaying ImportErrors until init time, rather than at import time.
    """
    msg = 'Dependencies are not installed for this feature'

    def _log_error():
        logger.error(msg)
        raise original_exception or ImportError(msg)

    class Placeholder:
        def __init__(self, *args, **kwargs):
            _log_error()

        def __getattr__(self, *args, **kwargs):
            _log_error()

        def dumps(self, *args, **kwargs):
            _log_error()

    return Placeholder


try:
    from .backends import *
    from .patcher import *
    from .models import *
    from .serializers import *
    from .session import ALL_METHODS, CachedSession, CacheMixin
# Log and ignore ImportErrors, if setup.py is invoked outside a virtualenv
except ImportError as e:
    logger.warning(e)
