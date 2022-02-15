"""
.. automodsumm:: requests_cache.serializers.pipeline
   :classes-only:
   :nosignatures:
"""
from typing import Any, Callable, Sequence, Union

from ..models import CachedResponse


class Stage:
    """Generic class to wrap serialization steps with consistent ``dumps()`` and ``loads()`` methods

    Args:
        obj: Serializer object or module, if applicable
        dumps: Serialization function, or name of method on ``obj``
        loads: Deserialization function, or name of method on ``obj``
    """

    def __init__(
        self,
        obj: Any = None,
        dumps: Union[str, Callable] = 'dumps',
        loads: Union[str, Callable] = 'loads',
    ):
        self.obj = obj
        self.dumps = getattr(obj, dumps) if isinstance(dumps, str) else dumps
        self.loads = getattr(obj, loads) if isinstance(loads, str) else loads


class SerializerPipeline:
    """A pipeline of stages chained together to serialize and deserialize response objects.

    Args:
        stages: A sequence of :py:class:`Stage` objects, or any objects with ``dumps()`` and
            ``loads()`` methods
        is_binary: Indicates whether the serialized content is binary
    """

    def __init__(self, stages: Sequence, is_binary: bool = False):
        self.is_binary = is_binary
        self.stages = stages
        self.dump_stages = [stage.dumps for stage in stages]
        self.load_stages = [stage.loads for stage in reversed(stages)]

    def dumps(self, value) -> Union[str, bytes]:
        for step in self.dump_stages:
            value = step(value)
        return value

    def loads(self, value) -> CachedResponse:
        for step in self.load_stages:
            value = step(value)
        return value
