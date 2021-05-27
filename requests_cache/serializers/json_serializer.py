# Use ultrajson, if installed, otherwise stdlib json
try:
    import ujson as json
    from cattr.preconf.ujson import make_converter
except ImportError:
    import json
    from cattr.preconf.json import make_converter

from ..models import CachedResponse
from .base import BaseSerializer


class JSONSerializer(BaseSerializer):
    """Serializer that converts responses to JSON"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, converter_factory=make_converter, **kwargs)

    def dumps(self, response: CachedResponse) -> bytes:
        return json.dumps(super().unstructure(response), indent=2)

    def loads(self, obj: bytes) -> CachedResponse:
        return super().structure(json.loads(obj))
