"""The ``cattrs`` library includes a number of `pre-configured converters
<https://cattrs.readthedocs.io/en/latest/preconf.html>`_ that perform some pre-serialization steps
required for specific serialization formats.

This module wraps those converters as serializer :py:class:`.Stage` objects. These are then used as
a stage in a :py:class:`.SerializerPipeline`, which runs after the base converter and before the
format's ``dumps()`` (or equivalent) method.

For any optional libraries that aren't installed, the corresponding serializer will be a placeholder
class that raises an ``ImportError`` at initialization time instead of at import time.

.. automodsumm:: requests_cache.serializers.preconf
   :nosignatures:
"""
import pickle
from functools import partial

from cattr.preconf import bson as bson_preconf
from cattr.preconf import json as json_preconf
from cattr.preconf import msgpack, orjson, pyyaml, tomlkit, ujson

from .._utils import get_placeholder_class
from .cattrs import CattrStage
from .pipeline import SerializerPipeline, Stage

base_stage = (
    CattrStage()
)  #: Base stage for all serializer pipelines (or standalone dict serializer)
dict_serializer = base_stage  #: Partial serializer that unstructures responses into dicts
bson_preconf_stage = CattrStage(bson_preconf.make_converter)  #: Pre-serialization steps for BSON
json_preconf_stage = CattrStage(json_preconf.make_converter)  #: Pre-serialization steps for JSON
msgpack_preconf_stage = CattrStage(msgpack.make_converter)  #: Pre-serialization steps for msgpack
orjson_preconf_stage = CattrStage(orjson.make_converter)  #: Pre-serialization steps for orjson
yaml_preconf_stage = CattrStage(pyyaml.make_converter)  #: Pre-serialization steps for YAML
toml_preconf_stage = CattrStage(tomlkit.make_converter)  #: Pre-serialization steps for TOML
ujson_preconf_stage = CattrStage(ujson.make_converter)  #: Pre-serialization steps for ultrajson
pickle_serializer = SerializerPipeline(
    [base_stage, pickle], is_binary=True
)  #: Complete pickle serializer
utf8_encoder = Stage(dumps=str.encode, loads=lambda x: x.decode())  #: Encode to bytes


# Safe pickle serializer
try:
    from itsdangerous import Signer

    def signer_stage(secret_key=None, salt='requests-cache') -> Stage:
        """Create a stage that uses ``itsdangerous`` to add a signature to responses on write, and
        validate that signature with a secret key on read. Can be used in a
        :py:class:`.SerializerPipeline` in combination with any other serialization steps.
        """
        return Stage(Signer(secret_key=secret_key, salt=salt), dumps='sign', loads='unsign')

    def safe_pickle_serializer(
        secret_key=None, salt='requests-cache', **kwargs
    ) -> SerializerPipeline:
        """Create a serializer that uses ``pickle`` + ``itsdangerous`` to add a signature to
        responses on write, and validate that signature with a secret key on read.
        """
        return SerializerPipeline(
            [base_stage, pickle, signer_stage(secret_key, salt)], is_binary=True
        )

except ImportError as e:
    signer_stage = get_placeholder_class(e)
    safe_pickle_serializer = get_placeholder_class(e)


# BSON serializer
try:
    try:
        from bson import json_util as bson
    except ImportError:
        import bson

    bson_serializer = SerializerPipeline(
        [bson_preconf_stage, bson], is_binary=False
    )  #: Complete BSON serializer; uses pymongo's ``bson.json_util`` if installed, otherwise standalone ``bson`` codec
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
    [_json_preconf_stage, _json_stage], is_binary=False
)  #: Complete JSON serializer; uses ultrajson if available


# YAML serializer
try:
    import yaml

    yaml_serializer = SerializerPipeline(
        [
            yaml_preconf_stage,
            Stage(yaml, loads='safe_load', dumps='safe_dump'),
        ],
        is_binary=False,
    )  #: Complete YAML serializer
except ImportError as e:
    yaml_serializer = get_placeholder_class(e)
