# ruff: noqa: F841
"""Stages and serializers for supported serialization formats.

.. automodsumm:: requests_cache.serializers.preconf
   :nosignatures:
"""

import json
import pickle
from functools import partial
from importlib import import_module

from .._utils import get_placeholder_class
from .cattrs import CattrStage, _convert_floats, make_decimal_timedelta_converter
from .pipeline import SerializerPipeline, Stage


def make_stage(preconf_module: str, **kwargs):
    """Create a preconf serializer stage from a module name, if dependencies are installed"""
    try:
        factory = import_module(preconf_module).make_converter
        return CattrStage(factory, **kwargs)
    except ImportError as e:
        return get_placeholder_class(e)


# Pre-serialization stages
base_stage = CattrStage()  #: Base stage for all serializer pipelines
utf8_encoder = Stage(dumps=str.encode, loads=lambda x: x.decode())  #: Encode to bytes
utf8_serializer = SerializerPipeline([utf8_encoder], 'utf8', is_binary=True)  #: Encode to bytes
bson_preconf_stage = make_stage(
    'cattr.preconf.bson', convert_datetime=False
)  #: Pre-serialization steps for BSON
json_preconf_stage = make_stage('cattr.preconf.json')  #: Pre-serialization steps for JSON
msgpack_preconf_stage = make_stage('cattr.preconf.msgpack')  #: Pre-serialization steps for msgpack
orjson_preconf_stage = make_stage('cattr.preconf.orjson')  #: Pre-serialization steps for orjson
toml_preconf_stage = make_stage('cattr.preconf.tomlkit')  #: Pre-serialization steps for TOML
ujson_preconf_stage = make_stage('cattr.preconf.ujson')  #: Pre-serialization steps for ultrajson
yaml_preconf_stage = make_stage('cattr.preconf.pyyaml')  #: Pre-serialization steps for YAML

# Basic serializers with no additional dependencies
dict_serializer = SerializerPipeline(
    [base_stage], name='dict', is_binary=False
)  #: Partial serializer that unstructures responses into dicts
pickle_serializer = SerializerPipeline(
    [base_stage, Stage(pickle)], name='pickle', is_binary=True
)  #: Pickle serializer


# Safe pickle serializer
def signer_stage(secret_key=None, salt='requests-cache') -> Stage:
    """Create a stage that uses ``itsdangerous`` to add a signature to responses on write, and
    validate that signature with a secret key on read. Can be used in a
    :py:class:`.SerializerPipeline` in combination with any other serialization steps.
    """
    from itsdangerous import Signer

    return Stage(
        Signer(secret_key=secret_key, salt=salt),
        dumps='sign',
        loads='unsign',
    )


def safe_pickle_serializer(secret_key=None, salt='requests-cache', **kwargs) -> SerializerPipeline:
    """Create a serializer that uses ``pickle`` + ``itsdangerous`` to add a signature to
    responses on write, and validate that signature with a secret key on read.
    """
    return SerializerPipeline(
        [base_stage, Stage(pickle), signer_stage(secret_key, salt)],
        name='safe_pickle',
        is_binary=True,
    )


try:
    import itsdangerous  # noqa: F401
except ImportError as e:
    signer_stage = get_placeholder_class(e)  # noqa: F811
    safe_pickle_serializer = get_placeholder_class(e)  # noqa: F811


# BSON/MongoDB document serializer
try:
    import bson

    bson_serializer = SerializerPipeline(
        [bson_preconf_stage, Stage(bson, dumps='encode', loads='decode')],
        name='bson',
        is_binary=True,
    )  #: Complete BSON serializer
    bson_document_serializer = SerializerPipeline(
        [bson_preconf_stage],
        name='bson_document',
        is_binary=False,
    )  #: BSON partial serializer that produces a MongoDB-compatible document
except ImportError as e:
    bson_serializer = get_placeholder_class(e)
    bson_document_serializer = get_placeholder_class(e)


# JSON serializer: stdlib
json_serializer = SerializerPipeline(
    [json_preconf_stage, Stage(dumps=partial(json.dumps, indent=2), loads=json.loads)],
    name='json',
    is_binary=False,
)  #: Complete JSON serializer using stdlib json module


# JSON serializer: ultrajson
try:
    import ujson

    ujson_serializer = SerializerPipeline(
        [ujson_preconf_stage, Stage(dumps=partial(ujson.dumps, indent=2), loads=ujson.loads)],
        name='ujson',
        is_binary=False,
    )  #: Complete JSON serializer using ultrajson module
except ImportError as e:
    ujson_serializer = get_placeholder_class(e)


# JSON serializer: orjson
try:
    import orjson

    orjson_serializer = SerializerPipeline(
        [
            orjson_preconf_stage,
            Stage(dumps=partial(orjson.dumps, option=orjson.OPT_INDENT_2), loads=orjson.loads),
        ],
        name='orjson',
        is_binary=True,
    )  #: Complete JSON serializer using orjson module
except ImportError as e:
    orjson_serializer = get_placeholder_class(e)


# YAML serializer
try:
    import yaml

    _yaml_stage = Stage(yaml, loads='safe_load', dumps='safe_dump')
    yaml_serializer = SerializerPipeline(
        [yaml_preconf_stage, _yaml_stage],
        name='yaml',
        is_binary=False,
    )  #: Complete YAML serializer
except ImportError as e:
    yaml_serializer = get_placeholder_class(e)


# DynamoDB document serializer
dynamodb_preconf_stage = CattrStage(
    factory=make_decimal_timedelta_converter, convert_timedelta=False
)  #: Pre-serialization steps for DynamoDB
convert_float_stage = Stage(dumps=_convert_floats, loads=lambda x: x)
dynamodb_document_serializer = SerializerPipeline(
    [dynamodb_preconf_stage, convert_float_stage],
    name='dynamodb_document',
    is_binary=False,
)  #: DynamoDB-compatible document serializer
