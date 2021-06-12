import bson
from cattr.preconf.bson import make_converter

from ..models import CachedResponse
from .base import BaseSerializer


class BSONSerializer(BaseSerializer):
    """Serializer that converts responses to JSON"""

    def __init__(self, *args, **kwargs):

        super().__init__(*args, converter_factory=make_converter, **kwargs)

    def dumps(self, response: CachedResponse) -> bytes:
        return bson.encode(super().dumps(response))

    def loads(self, obj: bytes) -> CachedResponse:
        return super().loads(bson.decode(obj))
