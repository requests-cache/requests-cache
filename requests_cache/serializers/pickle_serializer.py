import pickle
from typing import Iterable, Union

from itsdangerous.serializer import Serializer as SafeSerializer

from ..models import CachedResponse
from .base import BaseSerializer


class PickleSerializer(BaseSerializer):
    """Wrapper for pickle that pre/post-processes with cattrs"""

    def dumps(self, response: CachedResponse) -> bytes:
        return pickle.dumps(super().dumps(response))

    def loads(self, obj: bytes) -> CachedResponse:
        return super().loads(pickle.loads(obj))


class SafePickleSerializer(SafeSerializer, BaseSerializer):
    """Wrapper for itsdangerous + pickle that pre/post-processes with cattrs"""

    def __init__(
        self,
        *args,
        secret_key: Union[Iterable, str, bytes] = None,
        salt: Union[str, bytes] = None,
        **kwargs
    ):
        super().__init__(
            *args,
            secret_key=secret_key,
            salt=salt or b'requests-cache',
            **kwargs,
            serializer=PickleSerializer()
        )
