import pickle

from itsdangerous.serializer import Serializer as SafeSerializer

from ..models import CachedResponse
from .base import BaseSerializer


class PickleSerializer(BaseSerializer):
    """Wrapper for pickle that pre/post-processes with cattrs"""

    def dumps(self, response: CachedResponse) -> bytes:
        return pickle.dumps(super().unstructure(response))

    def loads(self, obj: bytes) -> CachedResponse:
        return super().structure(pickle.loads(obj))


class SafePickleSerializer(SafeSerializer, BaseSerializer):
    """Wrapper for itsdangerous + pickle that pre/post-processes with cattrs"""

    def __init__(self, *args, **kwargs):
        # super().__init__(*args, **kwargs, serializer=pickle)
        super().__init__(*args, **kwargs, serializer=PickleSerializer())

    # def dumps(self, response: CachedResponse) -> bytes:
    #     return SafeSerializer.dumps(self, super().unstructure(response))

    # def loads(self, obj: bytes) -> CachedResponse:
    #     return super().structure(SafeSerializer.loads(self, obj))
