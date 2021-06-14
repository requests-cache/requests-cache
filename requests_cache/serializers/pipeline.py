from typing import Any, Callable, List, Union

from ..models import CachedResponse


class Stage:
    # Generic utility class for aliasing dumps and loads to
    # other methods
    __slots__ = ['obj', 'dumps', 'loads', 'is_binary']
    obj: Any
    dumps: Callable
    loads: Callable
    is_binary: bool

    def __init__(self, obj: Any, dumps: str = "dumps", loads: str = "loads", is_binary=False):
        self.obj = obj
        self.dumps = getattr(obj, dumps)
        self.loads = getattr(obj, loads)
        self.is_binary = is_binary


class SerializerPipeline:
    def __init__(self, steps: List, is_binary=False):
        self.steps = steps
        self.dump_steps = [getattr(step, "dumps") for step in steps]
        self.load_steps = [getattr(step, "loads") for step in reversed(steps)]
        self.is_binary = is_binary

    def dumps(self, value) -> Union[str, bytes]:
        for step in self.dump_steps:
            value = step(value)
        return value

    def loads(self, value) -> CachedResponse:
        for step in self.load_steps:
            value = step(value)
        return value
