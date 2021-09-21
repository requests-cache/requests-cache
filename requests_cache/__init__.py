# flake8: noqa: E402,F401
from logging import getLogger
from typing import Callable, Iterable, Dict

logger = getLogger(__name__)

# Version is defined in pyproject.toml.
# It's copied here to make it easier for client code to check the installed version.
__version__ = '0.8.2'


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


def get_valid_kwargs(func: Callable, kwargs: Dict, extras: Iterable[str] = None) -> Dict:
    """Get the subset of non-None ``kwargs`` that are valid params for ``func``"""
    params = list(signature(func).parameters)
    params.extend(extras or [])
    return {k: v for k, v in kwargs.items() if k in params and v is not None}


try:
    from .backends import *
    from .cache_control import *
    from .cache_keys import *
    from .models import *
    from .patcher import *
    from .serializers import *
    from .session import *
# Log and ignore ImportErrors, if imported outside a virtualenv (e.g., just to check __version__)
except ImportError as e:
    logger.warning(e)
