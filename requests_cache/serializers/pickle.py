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


class SafePickleSerializer(BaseSerializer, SafeSerializer):
    """Wrapper for itsdangerous + pickle that pre/post-processes with cattrs"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, serializer=PickleSerializer())

    def dumps(self, response: CachedResponse) -> bytes:
        x = super().unstructure(response)
        # breakpoint()
        return SafeSerializer.dumps(self, x)

    # TODO: Something weird is going on here
    def loads(self, obj: bytes) -> CachedResponse:
        return SafeSerializer.loads(self, obj)
        # breakpoint()
        return super().structure(SafeSerializer.loads(self, obj))
