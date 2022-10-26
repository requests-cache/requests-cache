# flake8: noqa: F401, F403
from warnings import warn

from .policy import *

warn(
    DeprecationWarning(
        'Contents of requests_cache.cache_control will be moved in an upcoming release; '
        'please import members `from requests_cache` instead'
    )
)
