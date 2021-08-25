"""
.. automodsumm:: requests_cache.serializers.pipeline
   :classes-only:
   :nosignatures:
"""
from typing import Any, Callable, List, Union

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
    """A sequence of steps used to serialize and deserialize response objects.
    This can be initialized with :py:class:`Stage` objects, or any objects with ``dumps()`` and
    ``loads()`` methods
    """

    def __init__(self, stages: List):
        self.steps = stages
        self.dump_steps = [step.dumps for step in stages]
        self.load_steps = [step.loads for step in reversed(stages)]

    def dumps(self, value) -> Union[str, bytes]:
        for step in self.dump_steps:
            value = step(value)
        return value

    def loads(self, value) -> CachedResponse:
        for step in self.load_steps:
            value = step(value)
        return value
