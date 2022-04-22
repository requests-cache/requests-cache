"""Response serialization utilities. See :ref:`serializers` for general usage info.
"""
# flake8: noqa: F401
from typing import Union

from .cattrs import CattrStage
from .pipeline import SerializerPipeline, Stage
from .preconf import (
    bson_document_serializer,
    bson_serializer,
    dict_serializer,
    dynamodb_document_serializer,
    json_serializer,
    pickle_serializer,
    safe_pickle_serializer,
    utf8_encoder,
    yaml_serializer,
)

__all__ = [
    'SERIALIZERS',
    'CattrStage',
    'SerializerPipeline',
    'Stage',
    'bson_serializer',
    'bson_document_serializer',
    'dynamodb_document_serializer',
    'dict_serializer',
    'json_serializer',
    'pickle_serializer',
    'safe_pickle_serializer',
    'yaml_serializer',
    'init_serializer',
    'utf8_encoder',
]

SERIALIZERS = {
    'bson': bson_serializer,
    'json': json_serializer,
    'pickle': pickle_serializer,
    'yaml': yaml_serializer,
}

SerializerType = Union[str, SerializerPipeline, Stage]


def init_serializer(serializer: SerializerType = None):
    """Initialize a serializer from a name or instance"""
    if isinstance(serializer, str):
        serializer = SERIALIZERS[serializer]
    return serializer
