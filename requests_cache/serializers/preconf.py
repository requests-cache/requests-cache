# flake8: noqa: F841
"""The ``cattrs`` library includes a number of `pre-configured converters
<https://cattrs.readthedocs.io/en/latest/preconf.html>`_ that perform some pre-serialization steps
required for specific serialization formats.

This module wraps those converters as serializer :py:class:`.Stage` objects. These are then used as
stages in a :py:class:`.SerializerPipeline`, which runs after the base converter and before the
format's ``dumps()`` (or equivalent) method.

For any optional libraries that aren't installed, the corresponding serializer will be a placeholder
class that raises an ``ImportError`` at initialization time instead of at import time.

.. automodsumm:: requests_cache.serializers.preconf
   :nosignatures:
"""
import pickle
from datetime import timedelta
from decimal import Decimal
from functools import partial
from importlib import import_module

from cattr import GenConverter

from .._utils import get_placeholder_class
from .cattrs import CattrStage
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
bson_preconf_stage = make_stage('cattr.preconf.bson')  #: Pre-serialization steps for BSON
json_preconf_stage = make_stage('cattr.preconf.json')  #: Pre-serialization steps for JSON
msgpack_preconf_stage = make_stage('cattr.preconf.msgpack')  #: Pre-serialization steps for msgpack
orjson_preconf_stage = make_stage('cattr.preconf.orjson')  #: Pre-serialization steps for orjson
toml_preconf_stage = make_stage('cattr.preconf.tomlkit')  #: Pre-serialization steps for TOML
ujson_preconf_stage = make_stage('cattr.preconf.ujson')  #: Pre-serialization steps for ultrajson
yaml_preconf_stage = make_stage('cattr.preconf.pyyaml')  #: Pre-serialization steps for YAML

# Basic serializers with no additional dependencies
dict_serializer = SerializerPipeline(
    [base_stage], is_binary=False
)  #: Partial serializer that unstructures responses into dicts
pickle_serializer = SerializerPipeline(
    [base_stage, Stage(pickle)], is_binary=True
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
        is_binary=True,
    )


try:
    import itsdangerous  # noqa: F401
except ImportError as e:
    signer_stage = get_placeholder_class(e)
    safe_pickle_serializer = get_placeholder_class(e)


# BSON serializer
def _get_bson_functions():
    """Handle different function names between pymongo's bson and standalone bson"""
    try:
        import pymongo  # noqa: F401

        return {'dumps': 'encode', 'loads': 'decode'}
    except ImportError:
        return {'dumps': 'dumps', 'loads': 'loads'}


try:
    import bson

    bson_serializer = SerializerPipeline(
        [bson_preconf_stage, Stage(bson, **_get_bson_functions())],
        is_binary=True,
    )  #: Complete BSON serializer; uses pymongo's ``bson`` if installed, otherwise standalone ``bson`` codec
except ImportError as e:
    bson_serializer = get_placeholder_class(e)


# JSON serializer
try:
    import ujson as json

    _json_preconf_stage = ujson_preconf_stage
except ImportError:
    import json  # type: ignore

    _json_preconf_stage = json_preconf_stage

_json_stage = Stage(dumps=partial(json.dumps, indent=2), loads=json.loads)
json_serializer = SerializerPipeline(
    [_json_preconf_stage, _json_stage],
    is_binary=False,
)  #: Complete JSON serializer; uses ultrajson if available


# YAML serializer
try:
    import yaml

    _yaml_stage = Stage(yaml, loads='safe_load', dumps='safe_dump')
    yaml_serializer = SerializerPipeline(
        [yaml_preconf_stage, _yaml_stage],
        is_binary=False,
    )  #: Complete YAML serializer
except ImportError as e:
    yaml_serializer = get_placeholder_class(e)
