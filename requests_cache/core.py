"""Placeholder module for backwards-compatibility"""
import warnings

from .patcher import *  # noqa: F401, F403
from .session import *  # noqa: F401, F403

msg = 'The module `requests_cache.core` is deprecated; please import from `requests_cache`.'
warnings.warn(DeprecationWarning(msg))
