# flake8: noqa: F401
import pickle
from warnings import warn

from .. import get_placeholder_class
from .pipeline import SerializerPipeline, Stage

__all__ = [
    'SERIALIZERS',
    'CattrStage',
    'SerializerPipeline',
    'Stage',
    'bson_serializer',
    'json_serializer',
    'pickle_serializer',
    'safe_pickle_serializer',
    'yaml_serializer',
    'init_serializer',
]

# If cattrs isn't installed, use plain pickle for pickle_serializer, and placeholders for the rest.
# Additional checks for format-specific optional libraries are handled in the preconf module.
try:
    from .cattrs import CattrStage
    from .preconf import (
        bson_serializer,
        json_serializer,
        pickle_serializer,
        safe_pickle_serializer,
        yaml_serializer,
    )
except ImportError as e:
    CattrStage = get_placeholder_class(e)  # type: ignore
    bson_serializer = get_placeholder_class(e)
    json_serializer = get_placeholder_class(e)
    pickle_serializer = pickle  # type: ignore
    safe_pickle_serializer = get_placeholder_class(e)
    yaml_serializer = get_placeholder_class(e)


SERIALIZERS = {
    'bson': bson_serializer,
    'json': json_serializer,
    'pickle': pickle_serializer,
    'yaml': yaml_serializer,
}


def init_serializer(serializer=None, **kwargs):
    """Initialize a serializer from a name, class, or instance"""
    serializer = serializer or 'pickle'
    # Backwards=compatibility with 0.6; will be removed in 0.8
    if serializer == 'safe_pickle' or (serializer == 'pickle' and 'secret_key' in kwargs):
        serializer = safe_pickle_serializer(**kwargs)
        msg = (
            'Please initialize with safe_pickle_serializer(secret_key) instead. '
            'This usage is deprecated and will be removed in a future version.'
        )
        warn(DeprecationWarning(msg))
    elif isinstance(serializer, str):
        serializer = SERIALIZERS[serializer]
    return serializer
