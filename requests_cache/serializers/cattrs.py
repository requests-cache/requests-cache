"""
Utilities to break down :py:class:`.CachedResponse` objects into a dict of python builtin types
using `cattrs <https://cattrs.readthedocs.io>`_. This does the majority of the work needed for any
serialization format.

.. automodsumm:: requests_cache.serializers.cattrs
   :classes-only:
   :nosignatures:

.. automodsumm:: requests_cache.serializers.cattrs
   :functions-only:
   :nosignatures:
"""
from datetime import datetime, timedelta
from typing import Callable, Dict, ForwardRef, MutableMapping

from cattr import GenConverter
from requests.cookies import RequestsCookieJar, cookiejar_from_dict
from requests.structures import CaseInsensitiveDict
from urllib3._collections import HTTPHeaderDict

from ..models import CachedResponse
from .pipeline import Stage


class CattrStage(Stage):
    """Base serializer class that does pre/post-processing with  ``cattrs``. This can be used either
    on its own, or as a stage within a :py:class:`.SerializerPipeline`.
    """

    def __init__(self, factory: Callable[..., GenConverter] = None):
        self.converter = init_converter(factory)

    def dumps(self, value: CachedResponse) -> Dict:
        if not isinstance(value, CachedResponse):
            return value
        return self.converter.unstructure(value)

    def loads(self, value: Dict) -> CachedResponse:
        if not isinstance(value, MutableMapping):
            return value
        return self.converter.structure(value, cl=CachedResponse)


def init_converter(factory: Callable[..., GenConverter] = None):
    """Make a converter to structure and unstructure nested objects within a :py:class:`.CachedResponse`"""
    factory = factory or GenConverter
    converter = factory(omit_if_default=True)

    # Convert datetimes to and from iso-formatted strings
    converter.register_unstructure_hook(datetime, lambda obj: obj.isoformat() if obj else None)  # type: ignore
    converter.register_structure_hook(datetime, _to_datetime)

    # Convert timedeltas to and from float values in seconds
    converter.register_unstructure_hook(timedelta, lambda obj: obj.total_seconds() if obj else None)  # type: ignore
    converter.register_structure_hook(timedelta, _to_timedelta)

    # Convert dict-like objects to and from plain dicts
    converter.register_unstructure_hook(RequestsCookieJar, lambda obj: dict(obj.items()))  # type: ignore
    converter.register_structure_hook(RequestsCookieJar, lambda obj, cls: cookiejar_from_dict(obj))
    converter.register_unstructure_hook(CaseInsensitiveDict, dict)
    converter.register_structure_hook(
        CaseInsensitiveDict, lambda obj, cls: CaseInsensitiveDict(obj)
    )
    converter.register_unstructure_hook(HTTPHeaderDict, dict)
    converter.register_structure_hook(HTTPHeaderDict, lambda obj, cls: HTTPHeaderDict(obj))

    # Tell cattrs to resolve forward references (required for CachedResponse.history)
    converter.register_structure_hook_func(
        lambda cls: cls.__class__ is ForwardRef,
        lambda obj, cls: converter.structure(obj, cls.__forward_value__),
    )

    return converter


def _to_datetime(obj, cls) -> datetime:
    if isinstance(obj, str):
        obj = datetime.fromisoformat(obj)
    return obj


def _to_timedelta(obj, cls) -> timedelta:
    if isinstance(obj, (int, float)):
        obj = timedelta(seconds=obj)
    return obj
