"""Minor internal utility functions that don't really belong anywhere else"""

from contextlib import contextmanager
from inspect import signature
from logging import getLogger
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Tuple, Type

from urllib3 import filepost

FORM_BOUNDARY = '--requests-cache-form-boundary--'

KwargDict = Dict[str, Any]
logger = getLogger('requests_cache')


def chunkify(iterable: Optional[Iterable[Any]], max_size: int) -> Iterator[List[Any]]:
    """
    Split an iterable into chunks of a specified maximum size.

    Args:
        iterable: The iterable to split (converted to a list if not None).
        max_size: Maximum size of each chunk.

    Yields:
        Lists of items, each with length <= max_size.

    Raises:
        ValueError: If max_size is less than 1.
    """
    if max_size < 1:
        raise ValueError("max_size must be a positive integer")
    items = list(iterable or [])
    for index in range(0, len(items), max_size):
        yield items[index:index + max_size]


def coalesce(*values: Any, default: Any = None) -> Any:
    """
    Return the first non-None value from a sequence, or a default if all are None.

    Args:
        *values: Variable number of values to check.
        default: Value to return if all inputs are None.

    Returns:
        The first non-None value, or default if all are None.
    """
    return next((v for v in values if v is not None), default)


def decode(value: Any, encoding: str = 'utf-8') -> str:
    """
    Decode a value to a string if it's bytes, otherwise return as-is.

    Args:
        value: The value to decode (bytes or str).
        encoding: Encoding to use for decoding (default: 'utf-8').

    Returns:
        Decoded string or empty string if value is falsy.
    """
    if not value:
        return ''
    return value.decode(encoding) if isinstance(value, bytes) else str(value)


def encode(value: Any, encoding: str = 'utf-8') -> bytes:
    """
    Encode a value to bytes if it’s not already bytes.

    Args:
        value: The value to encode (str or bytes).
        encoding: Encoding to use (default: 'utf-8').

    Returns:
        Bytes representation or empty bytes if value is falsy.
    """
    if not value:
        return b''
    return value if isinstance(value, bytes) else str(value).encode(encoding)


def get_placeholder_class(original_exception: Optional[Exception] = None) -> Type:
    """
    Create a placeholder class that raises an error on use, for missing dependencies.

    Args:
        original_exception: The exception to raise (defaults to ImportError).

    Returns:
        A class that logs an error and raises an exception when instantiated or used.
    """
    def _log_error() -> None:
        msg = 'Dependencies are not installed for this feature'
        logger.error(msg)
        raise original_exception or ImportError(msg)

    class Placeholder:
        name = 'placeholder'

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            _log_error()

        def dumps(self, *args: Any, **kwargs: Any) -> None:
            _log_error()

        def loads(self, *args: Any, **kwargs: Any) -> None:
            _log_error()

    return Placeholder


def get_valid_kwargs(
    func: Callable[..., Any], 
    kwargs: Dict[str, Any], 
    extras: Optional[Iterable[str]] = None
) -> KwargDict:
    """
    Extract valid, non-None keyword arguments for a function.

    Args:
        func: The function to check arguments against.
        kwargs: Dictionary of keyword arguments.
        extras: Additional valid parameter names (optional).

    Returns:
        Dictionary of valid, non-None kwargs.
    """
    valid_kwargs, _ = split_kwargs(func, kwargs, extras)
    return {k: v for k, v in valid_kwargs.items() if v is not None}


@contextmanager
def patch_form_boundary() -> Iterator[None]:
    """
    Temporarily patch urllib3's form boundary for multipart uploads.

    Yields:
        None, while the patch is active.

    Notes:
        Restores the original boundary after the context exits.
    """
    original_boundary = filepost.choose_boundary
    filepost.choose_boundary = lambda: FORM_BOUNDARY
    try:
        yield
    finally:
        filepost.choose_boundary = original_boundary


def split_kwargs(
    func: Callable[..., Any], 
    kwargs: Dict[str, Any], 
    extras: Optional[Iterable[str]] = None
) -> Tuple[KwargDict, KwargDict]:
    """
    Split kwargs into valid and invalid sets based on a function's signature.

    Args:
        func: The function to validate kwargs against.
        kwargs: Dictionary of keyword arguments.
        extras: Additional valid parameter names (optional).

    Returns:
        Tuple of (valid_kwargs, invalid_kwargs).
    """
    params = list(signature(func).parameters.keys())
    params.extend(extras or [])
    valid_kwargs = {k: v for k, v in kwargs.items() if k in params}
    invalid_kwargs = {k: v for k, v in kwargs.items() if k not in params}
    return valid_kwargs, invalid_kwargs


def try_int(value: Any) -> Optional[int]:
    """
    Attempt to convert a value to an integer.

    Args:
        value: The value to convert.

    Returns:
        Integer if conversion succeeds, None otherwise.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def is_json_content_type(content_type: Optional[str]) -> bool:
    """
    Check if a content-type string represents JSON.

    Args:
        content_type: The content-type string to check (e.g., 'application/json').

    Returns:
        True if the content-type is JSON-related, False otherwise.
    """
    if not content_type:
        return False
    return content_type.startswith('application/') and 'json' in content_type.lower()