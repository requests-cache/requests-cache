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

    is_binary = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, converter_factory=make_converter, **kwargs)

    def dumps(self, response: CachedResponse) -> str:
        return json.dumps(super().dumps(response), indent=2)

    def loads(self, obj: str) -> CachedResponse:
        return super().loads(json.loads(obj))
