import pickle

from .. import get_placeholder_class
from . import preconf
from .pipeline import SerializerPipeline, Stage

pickle_serializer = pickle

try:
    from itsdangerous import Signer

    def safe_pickle_serializer(secret_key=None, salt="requests-cache", **kwargs):
        if not secret_key:
            raise ValueError("Cannot use itsdangerous without a secret key!")
        return SerializerPipeline(
            [
                pickle_serializer,
                Stage(Signer(secret_key=secret_key, salt=salt), dumps='sign', loads='unsign'),
            ],
        )


except ImportError as e:
    safe_pickle_serializer = get_placeholder_class(e)


try:
    import ujson as json

    json_serializer = SerializerPipeline(
        [
            preconf.ujson_converter,  # CachedResponse -> JSON
            json,  # JSON -> str
        ],
    )
except ImportError:
    import json

    json_serializer = SerializerPipeline(
        [
            preconf.json_converter,  # CachedResponse -> JSON
            json,  # JSON -> str
        ],
    )

try:
    import bson.json_util

    bson_serializer = SerializerPipeline(
        [
            preconf.bson_converter,  # CachedResponse -> BSON
            bson.json_util,  # BSON -> str
        ],
    )
except ImportError as e:
    bson_serializer = get_placeholder_class(e)

try:
    import yaml

    yaml_serializer = SerializerPipeline(
        [preconf.pyyaml_converter, Stage(yaml, loads='load', dumps='dump')]
    )
except ImportError as e:
    yaml_serializer = get_placeholder_class(e)


SERIALIZERS = {
    "pickle": pickle_serializer,
    "safe_pickle": safe_pickle_serializer,
    "json": json_serializer,
    "bson": bson_serializer,
    "yaml": yaml_serializer,
}
