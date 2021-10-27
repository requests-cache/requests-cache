"""Miscellaneous minor utility functions that don't really belong anywhere else"""
from inspect import signature
from logging import getLogger
from typing import Any, Callable, Dict, Iterable, Iterator, List

logger = getLogger('requests_cache')


def chunkify(iterable: Iterable, max_size: int) -> Iterator[List]:
    """Split an iterable into chunks of a max size"""
    iterable = list(iterable)
    for index in range(0, len(iterable), max_size):
        yield iterable[index : index + max_size]


def coalesce(*values: Any, default=None) -> Any:
    """Get the first non-``None`` value in a list of values"""
    return next((v for v in values if v is not None), default)


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
