# flake8: noqa: E402,F401
from logging import getLogger

logger = getLogger('requests_cache')

# Version is defined in pyproject.toml.
# It's copied here to make it easier for client code to check the installed version.
__version__ = '0.9.2'

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
