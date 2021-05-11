# flake8: noqa: F401
import attr

dataclass = attr.s(
    auto_attribs=False,
    auto_detect=True,
    collect_by_mro=True,
    kw_only=True,
    slots=True,
    weakref_slot=False,
)


from .raw_response import CachedHTTPResponse
from .request import CachedRequest
from .response import CachedResponse
