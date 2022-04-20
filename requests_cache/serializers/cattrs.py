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
from decimal import Decimal
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

    def __init__(self, factory: Callable[..., GenConverter] = None, **kwargs):
        self.converter = init_converter(factory, **kwargs)

    def dumps(self, value: CachedResponse) -> Dict:
        if not isinstance(value, CachedResponse):
            return value
        return self.converter.unstructure(value)

    def loads(self, value: Dict) -> CachedResponse:
        if not isinstance(value, MutableMapping):
            return value
        return self.converter.structure(value, cl=CachedResponse)


def init_converter(
    factory: Callable[..., GenConverter] = None,
    convert_datetime: bool = True,
    convert_timedelta: bool = True,
) -> GenConverter:
    """Make a converter to structure and unstructure nested objects within a
    :py:class:`.CachedResponse`

    Args:
        factory: An optional factory function that returns a ``cattrs`` converter
        convert_datetime: May be set to ``False`` for pre-configured converters that already have
            datetime support
    """
    factory = factory or GenConverter
    converter = factory(omit_if_default=True)

    # Convert datetimes to and from iso-formatted strings
    if convert_datetime:
        converter.register_unstructure_hook(datetime, lambda obj: obj.isoformat() if obj else None)
        converter.register_structure_hook(datetime, _to_datetime)

    # Convert timedeltas to and from float values in seconds
    if convert_timedelta:
        converter.register_unstructure_hook(
            timedelta, lambda obj: obj.total_seconds() if obj else None
        )
        converter.register_structure_hook(timedelta, _to_timedelta)

    # Convert dict-like objects to and from plain dicts
    converter.register_unstructure_hook(RequestsCookieJar, lambda obj: dict(obj.items()))
    converter.register_structure_hook(RequestsCookieJar, lambda obj, cls: cookiejar_from_dict(obj))
    converter.register_unstructure_hook(CaseInsensitiveDict, dict)
    converter.register_structure_hook(
        CaseInsensitiveDict, lambda obj, cls: CaseInsensitiveDict(obj)
    )
    converter.register_unstructure_hook(HTTPHeaderDict, dict)
    converter.register_structure_hook(HTTPHeaderDict, lambda obj, cls: HTTPHeaderDict(obj))

    # Resolve forward references (required for CachedResponse.history)
    converter.register_unstructure_hook_func(
        lambda cls: cls.__class__ is ForwardRef,
        lambda obj, cls=None: converter.unstructure(obj, cls.__forward_value__ if cls else None),
    )
    converter.register_structure_hook_func(
        lambda cls: cls.__class__ is ForwardRef,
        lambda obj, cls: converter.structure(obj, cls.__forward_value__),
    )
    return converter


def make_decimal_timedelta_converter(**kwargs) -> GenConverter:
    """Make a converter that uses Decimals instead of floats to represent timedelta objects"""
    converter = GenConverter(**kwargs)
    converter.register_unstructure_hook(
        timedelta, lambda obj: Decimal(str(obj.total_seconds())) if obj else None
    )
    converter.register_structure_hook(timedelta, _to_timedelta)
    return converter


def _to_datetime(obj, cls) -> datetime:
    if isinstance(obj, str):
        obj = datetime.fromisoformat(obj)
    return obj


def _to_timedelta(obj, cls) -> timedelta:
    if isinstance(obj, (int, float)):
        obj = timedelta(seconds=obj)
    elif isinstance(obj, Decimal):
        obj = timedelta(seconds=float(obj))
    return obj
