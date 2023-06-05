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
from json import JSONDecodeError
from typing import Callable, Dict, ForwardRef, MutableMapping, Optional

from cattr import Converter
from requests.cookies import RequestsCookieJar, cookiejar_from_dict
from requests.exceptions import RequestException
from requests.structures import CaseInsensitiveDict

from ..models import CachedResponse, DecodedContent
from .pipeline import Stage

try:
    import ujson as json
except ImportError:
    import json  # type: ignore


class CattrStage(Stage):
    """Base serializer class that does pre/post-processing with  ``cattrs``. This can be used either
    on its own, or as a stage within a :py:class:`.SerializerPipeline`.

    Args:
        factory: A callable that returns a ``cattrs`` converter to start from instead of a new
            ``Converter``. Mainly useful for preconf converters.
        decode_content: Save response body in human-readable format, if possible

    Notes on ``decode_content`` option:

    * Response body will be decoded into a human-readable format (if possible) during serialization,
      and re-encoded during deserialization to reconstruct the original response.
    * Supported  Content-Types are ``application/json`` and ``text/*``. All other types will be saved as-is.
    * Decoded responses are saved in a separate ``_decoded_content`` attribute, to ensure that
      ``_content`` is always binary.
    * This is the default behavior for Filesystem, DynamoDB, and MongoDB backends.
    """

    def __init__(
        self,
        factory: Optional[Callable[..., Converter]] = None,
        decode_content: bool = False,
        **kwargs
    ):
        self.converter = init_converter(factory, **kwargs)
        self.decode_content = decode_content

    def dumps(self, value: CachedResponse) -> Dict:
        if not isinstance(value, CachedResponse):
            return value
        response_dict = self.converter.unstructure(value)
        return _decode_content(value, response_dict) if self.decode_content else response_dict

    def loads(self, value: Dict) -> CachedResponse:
        if not isinstance(value, MutableMapping):
            return value
        return _encode_content(self.converter.structure(value, cl=CachedResponse))


def init_converter(
    factory: Optional[Callable[..., Converter]] = None,
    convert_datetime: bool = True,
    convert_timedelta: bool = True,
) -> Converter:
    """Make a converter to structure and unstructure nested objects within a
    :py:class:`.CachedResponse`

    Args:
        factory: An optional factory function that returns a ``cattrs`` converter
        convert_datetime: May be set to ``False`` for pre-configured converters that already have
            datetime support
    """
    factory = factory or Converter
    try:
        converter = factory(omit_if_default=True)
    # Handle previous versions of cattrs (<22.2) that don't support this argument
    except TypeError:
        converter = factory()

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

    # Convert decoded JSON body back to a string. If the object is a valid JSON root (dict or list),
    # that means it was previously saved in human-readable format due to `decode_content=True`.
    # After this hook runs, the body will also be re-encoded with `_encode_content()`.
    converter.register_structure_hook(
        DecodedContent, lambda obj, cls: json.dumps(obj) if isinstance(obj, (dict, list)) else obj
    )

    def structure_fwd_ref(obj, cls):
        # python<=3.8: ForwardRef may not have been evaluated yet
        if not cls.__forward_evaluated__:  # pragma: no cover
            cls._evaluate(globals(), locals())
        return converter.structure(obj, cls.__forward_value__)

    # Resolve forward references (required for CachedResponse.history)
    converter.register_unstructure_hook_func(
        lambda cls: cls.__class__ is ForwardRef,
        lambda obj, cls=None: converter.unstructure(obj, cls.__forward_value__ if cls else None),
    )
    converter.register_structure_hook_func(
        lambda cls: cls.__class__ is ForwardRef,
        structure_fwd_ref,
    )

    return converter


def make_decimal_timedelta_converter(**kwargs) -> Converter:
    """Make a converter that uses Decimals instead of floats to represent timedelta objects"""
    converter = Converter(**kwargs)
    converter.register_unstructure_hook(
        timedelta, lambda obj: Decimal(str(obj.total_seconds())) if obj else None
    )
    converter.register_structure_hook(timedelta, _to_timedelta)
    return converter


def _decode_content(response: CachedResponse, response_dict: Dict) -> Dict:
    """Decode response body into a human-readable format, if possible"""
    # Decode body as JSON
    if response.headers.get('Content-Type') == 'application/json':
        try:
            response_dict['_decoded_content'] = response.json()
            response_dict.pop('_content', None)
        except (JSONDecodeError, RequestException):
            pass

    # Decode body as text
    if response.headers.get('Content-Type', '').startswith('text/'):
        response_dict['_decoded_content'] = response.text
        response_dict.pop('_content', None)

    # Otherwise, it is most likely a binary body
    return response_dict


def _encode_content(response: CachedResponse) -> CachedResponse:
    """Re-encode response body if saved as JSON or text (via ``decode_content=True``).
    This has no effect for a binary response body.
    """
    if isinstance(response._decoded_content, str):
        response._content = response._decoded_content.encode('utf-8')
        response._decoded_content = None
        response.encoding = 'utf-8'  # Set encoding explicitly so requests doesn't have to guess
        response.headers['Content-Length'] = str(len(response._content))  # Size may have changed
    return response


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
