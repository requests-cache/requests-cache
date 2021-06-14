import datetime
import importlib
import pkgutil
from functools import partial
from pathlib import Path
from typing import ForwardRef

from cattr import GenConverter, preconf
from requests.cookies import RequestsCookieJar, cookiejar_from_dict
from requests.structures import CaseInsensitiveDict
from urllib3.response import HTTPHeaderDict

from ..models import CachedResponse
from .pipeline import Stage


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

    converter.register_structure_hook(
        ForwardRef('CachedResponse'),
        lambda obj, cls: converter.structure(obj, CachedResponse),
    )
    converter = CattrsStage(converter, dumps='unstructure', loads='structure', is_binary=False)

    return converter


preconf_module_names = list(m.name for m in pkgutil.iter_modules((Path(preconf.__file__).parent,)))

GLOBALS = globals()
for preconf_module_name in preconf_module_names:
    preconf_module = importlib.import_module(f"cattr.preconf.{preconf_module_name}")
    converter = preconf_module.make_converter
    GLOBALS[f"{preconf_module_name}_converter"] = init_converter(preconf_module.make_converter)
