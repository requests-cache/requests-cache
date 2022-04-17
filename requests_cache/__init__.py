# flake8: noqa: E402,F401
from logging import getLogger

# Version is defined in pyproject.toml.
# It's copied here to make it easier for client code to check the installed version.
__version__ = '0.10.0'

try:
    from .backends import *
    from .cache_keys import *
    from .models import *
    from .patcher import *
    from .policy import *
    from .serializers import *
    from .session import *
# Log and ignore ImportErrors, if imported outside a virtualenv (e.g., just to check __version__)
except ImportError as e:
    getLogger('requests_cache').warning(e, exc_info=True)
