from datetime import datetime, timedelta
from typing import Any, Callable

from requests.cookies import RequestsCookieJar, cookiejar_from_dict
from requests.structures import CaseInsensitiveDict
from urllib3.response import HTTPHeaderDict

from ..models import CachedResponse


class BaseSerializer:
    """Base serializer class for :py:class:`.CachedResponse` that optionally does
    pre/post-processing with cattrs. This provides an easy starting point for alternative
    serialization formats, and potential for some backend-specific optimizations.

    Subclasses must call and override ``dumps`` and ``loads`` methods.
    """

    # Flag to indicate to backends that content should be stored as a binary object
    is_binary = True

    def __init__(self, *args, converter_factory=None, **kwargs):
        self.converter = init_converter(factory=converter_factory)

    def dumps(self, obj: Any) -> Any:
        if not isinstance(obj, CachedResponse) or not self.converter:
            return obj
        return self.converter.unstructure(obj)

    def loads(self, obj: Any) -> Any:
        if not isinstance(obj, dict) or not self.converter:
            return obj
        return self.converter.structure(obj, CachedResponse)


def init_converter(factory: Callable = None):
    """Make a converter to structure and unstructure some of the nested objects within a response,
    if cattrs is installed.
    """
    try:
        from typing import ForwardRef

        from cattr import GenConverter
    except ImportError:
        return None

    factory = factory or GenConverter
    converter = factory(omit_if_default=True)

    # Convert datetimes to and from iso-formatted strings
    converter.register_unstructure_hook(datetime, lambda obj: obj.isoformat() if obj else None)
    converter.register_structure_hook(datetime, to_datetime)

    # Convert timedeltas to and from float values in seconds
    converter.register_unstructure_hook(timedelta, lambda obj: obj.total_seconds() if obj else None)
    converter.register_structure_hook(timedelta, to_timedelta)

    # Convert dict-like objects to and from plain dicts
    converter.register_unstructure_hook(RequestsCookieJar, lambda obj: dict(obj.items()))
    converter.register_structure_hook(RequestsCookieJar, lambda obj, cls: cookiejar_from_dict(obj))
    converter.register_unstructure_hook(CaseInsensitiveDict, dict)
    converter.register_structure_hook(CaseInsensitiveDict, lambda obj, cls: CaseInsensitiveDict(obj))
    converter.register_unstructure_hook(HTTPHeaderDict, dict)
    converter.register_structure_hook(HTTPHeaderDict, lambda obj, cls: HTTPHeaderDict(obj))

    converter.register_structure_hook(
        ForwardRef('CachedResponse'),
        lambda obj, cls: converter.structure(obj, CachedResponse),
    )

    return converter


def to_datetime(obj, cls) -> datetime:
    if isinstance(obj, str):
        obj = datetime.fromisoformat(obj)
    return obj


def to_timedelta(obj, cls) -> timedelta:
    if isinstance(obj, (int, float)):
        obj = timedelta(seconds=obj)
    return obj
