"""
Utilities to break down :py:class:`.CachedResponse` objects into a dict of python builtin types
using `cattrs <https://cattrs.readthedocs.io>`_. This does the majority of the work needed for all
serialization formats.

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
from requests.exceptions import JSONDecodeError
from requests.structures import CaseInsensitiveDict
from urllib3._collections import HTTPHeaderDict

from ..models import CachedResponse
from .pipeline import Stage

try:
    import ujson as json
except ImportError:
    import json  # type: ignore


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


class DecodedBodyStage(CattrStage):
    """Converter that decodes the response body into a human-readable format (if possible) when
    serializing, and re-encodes it to reconstruct the original response. Supported Content-Types
    are ``application/json`` and ``text/*``. All other types will be saved as-is.

    Notes:

    * This needs access to the response object for decoding, so this is used _instead_ of
      CattrStage, not before/after it.
    * Decoded responses are saved in a separate ``_decoded_content`` attribute, to ensure that
      ``_content`` is always binary.
    """

    def dumps(self, value: CachedResponse) -> Dict:
        response_dict = super().dumps(value)

        # Decode body as JSON
        if value.headers.get('Content-Type') == 'application/json':
            try:
                response_dict['_decoded_content'] = value.json()
                response_dict.pop('_content', None)
            except JSONDecodeError:
                pass

        # Decode body as text
        if value.headers.get('Content-Type', '').startswith('text/'):
            response_dict['_decoded_content'] = value.text
            response_dict.pop('_content', None)

        # Otherwise, it is most likely a binary body
        return response_dict

    def loads(self, value: Dict) -> CachedResponse:
        # Re-encode JSON and text bodies
        if isinstance(value.get('_decoded_content'), dict):
            value['_decoded_content'] = json.dumps(value['_decoded_content'])

        if isinstance(value.get('_decoded_content'), str):
            response = super().loads(value)
            response._content = response._decoded_content.encode('utf-8')
            response._decoded_content = ''
            response.encoding = 'utf-8'  # Set encoding explicitly so requests doesn't have to guess
            return response
        else:
            return super().loads(value)


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
