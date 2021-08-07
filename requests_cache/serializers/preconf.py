"""The ``cattrs`` library includes a number of pre-configured converters that perform some
additional steps required for specific serialization formats.

This module wraps those converters as serializer :py:class:`.Stage` objects. These are then used as
a stage in a :py:class:`.SerializerPipeline`, which runs after the base converter and before the
format's ``dumps()`` (or equivalent) method.

For any optional libraries that aren't installed, the corresponding serializer will be a placeholder
class that raises an ``ImportError`` at initialization time instead of at import time.

Requires python 3.7+.
"""
import pickle
from functools import partial

from cattr.preconf import bson as bson_preconf
from cattr.preconf import json as json_preconf
from cattr.preconf import msgpack, orjson, pyyaml, tomlkit, ujson

from .. import get_placeholder_class
from .cattrs import CattrStage
from .pipeline import SerializerPipeline, Stage

base_stage = CattrStage()  #: Base stage for all serializer pipelines
bson_preconf_stage = CattrStage(bson_preconf.make_converter)  #: Pre-configured stage for BSON
json_preconf_stage = CattrStage(json_preconf.make_converter)  #: Pre-configured stage for JSON
msgpack_preconf_stage = CattrStage(msgpack.make_converter)  #: Pre-configured stage for msgpack
orjson_preconf_stage = CattrStage(orjson.make_converter)  #: Pre-configured stage for orjson
yaml_preconf_stage = CattrStage(pyyaml.make_converter)  #: Pre-configured stage for YAML
toml_preconf_stage = CattrStage(tomlkit.make_converter)  #: Pre-configured stage for TOML
ujson_preconf_stage = CattrStage(ujson.make_converter)  #: Pre-configured stage for ujson


# Pickle serializer that uses the cattrs base converter
pickle_serializer = SerializerPipeline([base_stage, pickle])


# Pickle serializer with an additional stage using itsdangerous
try:
    from itsdangerous import Signer

    def signer_stage(secret_key=None, salt='requests-cache'):
        return Stage(Signer(secret_key=secret_key, salt=salt), dumps='sign', loads='unsign')

    def safe_pickle_serializer(secret_key=None, salt='requests-cache', **kwargs):
        """Create a serializer that uses ``itsdangerous`` to add a signature to responses during
        writes, and validate that signature with a secret key during reads.
        """
        return SerializerPipeline([base_stage, pickle, signer_stage(secret_key, salt)])


except ImportError as e:
    signer_stage = get_placeholder_class(e)
    safe_pickle_serializer = get_placeholder_class(e)


# BSON serializer using either PyMongo's bson.json_util if installed, otherwise standalone bson codec
try:
    try:
        from bson import json_util as bson
    except ImportError:
        import bson

    bson_serializer = SerializerPipeline([bson_preconf_stage, bson])
except ImportError as e:
    bson_serializer = get_placeholder_class(e)


# JSON serailizer using ultrajson if installed, otherwise stdlib json
try:
    import ujson as json

    converter = ujson_preconf_stage
except ImportError:
    import json  # type: ignore

    converter = json_preconf_stage

json_stage = Stage(json)
json_stage.dumps = partial(json.dumps, indent=2)
json_serializer = SerializerPipeline([converter, json_stage])


# YAML serializer using pyyaml
try:
    import yaml

    yaml_serializer = SerializerPipeline(
        [yaml_preconf_stage, Stage(yaml, loads='safe_load', dumps='safe_dump')]
    )
except ImportError as e:
    yaml_serializer = get_placeholder_class(e)
