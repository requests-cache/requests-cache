# flake8: noqa: F401
from logging import getLogger
from typing import Type, Union

from .. import get_placeholder_class
from .base import BaseSerializer
from .pickle_serializer import PickleSerializer, SafePickleSerializer

SerializerSpecifier = Union[str, BaseSerializer, Type[BaseSerializer]]
logger = getLogger(__name__)

try:
    from .bson_serializer import BSONSerializer
except ImportError as e:
    BSONSerializer = get_placeholder_class(e)  # type: ignore
try:
    from .json_serializer import JSONSerializer
except ImportError as e:
    JSONSerializer = get_placeholder_class(e)  # type: ignore


SERIALIZER_CLASSES = {
    'bson': BSONSerializer,
    'json': JSONSerializer,
    'pickle': PickleSerializer,
    'safe_pickle': SafePickleSerializer,
}


def init_serializer(serializer: SerializerSpecifier = None, *args, **kwargs) -> BaseSerializer:
    """Initialize a serializer from a name, class, or instance"""
    logger.debug(f'Initializing serializer: {serializer}')

    # Determine serializer class
    if isinstance(serializer, BaseSerializer):
        return serializer
    elif isinstance(serializer, type):
        return serializer(*args, **kwargs)
    # If no serializer is specified and a secret key is available, use itsdangerous; otherwise pickle
    elif not serializer:
        serializer = 'safe_pickle' if kwargs.get('secret_key') else 'pickle'

    serializer = str(serializer).lower()
    if serializer not in SERIALIZER_CLASSES:
        raise ValueError(f'Invalid serializer: {serializer}. Choose from: {SERIALIZER_CLASSES.keys()}')

    return SERIALIZER_CLASSES[serializer](*args, **kwargs)
