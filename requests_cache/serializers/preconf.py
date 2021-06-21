import datetime
from functools import partial

from requests.cookies import RequestsCookieJar, cookiejar_from_dict
from requests.structures import CaseInsensitiveDict
from urllib3.response import HTTPHeaderDict

from .. import get_placeholder_class
from ..models import CachedResponse
from .pipeline import Stage

try:
    from typing import ForwardRef

    from cattr import GenConverter
    from cattr.preconf import bson, json, msgpack, orjson, pyyaml, tomlkit, ujson

    def to_datetime(obj, cls) -> datetime:
        if isinstance(obj, str):
            obj = datetime.fromisoformat(obj)
        return obj

    def to_timedelta(obj, cls) -> datetime.timedelta:
        if isinstance(obj, (int, float)):
            obj = datetime.timedelta(seconds=obj)
        return obj

    class CattrsStage(Stage):
        def __init__(self, converter, *args, **kwargs):
            super().__init__(converter, *args, **kwargs)
            self.loads = partial(converter.structure, cl=CachedResponse)

    def init_converter(factory: GenConverter = None):
        """Make a converter to structure and unstructure some of the nested objects within a response,
        if cattrs is installed.
        """
        converter = factory(omit_if_default=True)

        # Convert datetimes to and from iso-formatted strings
        converter.register_unstructure_hook(datetime, lambda obj: obj.isoformat() if obj else None)
        converter.register_structure_hook(datetime, to_datetime)

        # Convert timedeltas to and from float values in seconds
        converter.register_unstructure_hook(
            datetime.timedelta, lambda obj: obj.total_seconds() if obj else None
        )
        converter.register_structure_hook(datetime.timedelta, to_timedelta)

        # Convert dict-like objects to and from plain dicts
        converter.register_unstructure_hook(RequestsCookieJar, lambda obj: dict(obj.items()))
        converter.register_structure_hook(RequestsCookieJar, lambda obj, cls: cookiejar_from_dict(obj))
        converter.register_unstructure_hook(CaseInsensitiveDict, dict)
        converter.register_structure_hook(CaseInsensitiveDict, lambda obj, cls: CaseInsensitiveDict(obj))
        converter.register_unstructure_hook(HTTPHeaderDict, dict)
        converter.register_structure_hook(HTTPHeaderDict, lambda obj, cls: HTTPHeaderDict(obj))

        # Tell cattrs that a 'CachedResponse' forward ref is equivalent to the CachedResponse class
        converter.register_structure_hook(
            ForwardRef('CachedResponse'),
            lambda obj, cls: converter.structure(obj, CachedResponse),
        )
        converter = CattrsStage(converter, dumps='unstructure', loads='structure')

        return converter

    bson_converter = init_converter(bson.make_converter)
    json_converter = init_converter(json.make_converter)
    msgpack_converter = init_converter(msgpack.make_converter)
    orjson_converter = init_converter(orjson.make_converter)
    pyyaml_converter = init_converter(pyyaml.make_converter)
    tomlkit_converter = init_converter(tomlkit.make_converter)
    ujson_converter = init_converter(ujson.make_converter)

except ImportError as e:
    bson_converter = get_placeholder_class(e)
    json_converter = get_placeholder_class(e)
    msgpack_converter = get_placeholder_class(e)
    orjson_converter = get_placeholder_class(e)
    pyyaml_converter = get_placeholder_class(e)
    tomlkit_converter = get_placeholder_class(e)
    ujson_converter = get_placeholder_class(e)
