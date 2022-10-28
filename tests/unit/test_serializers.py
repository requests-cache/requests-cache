# Note: Almost all serializer logic is covered by parametrized integration tests.
# Any additional serializer-specific tests can go here.
import gzip
import json
import pickle
import sys
from importlib import reload
from unittest.mock import patch
from uuid import uuid4

import pytest
from cattr import BaseConverter, GenConverter

from requests_cache import (
    CachedResponse,
    CachedSession,
    CattrStage,
    SerializerPipeline,
    Stage,
    json_serializer,
    safe_pickle_serializer,
    utf8_encoder,
)
from tests.conftest import skip_missing_deps


def test_stdlib_json():
    import requests_cache.serializers.preconf

    with patch.dict(sys.modules, {'ujson': None, 'cattr.preconf.ujson': None}):
        reload(requests_cache.serializers.preconf)
        from requests_cache.serializers.preconf import json as module_json

        assert module_json is json

    reload(requests_cache.serializers.preconf)


@skip_missing_deps('ujson')
def test_ujson():
    import ujson

    from requests_cache.serializers.preconf import json as module_json

    assert module_json is ujson


@skip_missing_deps('bson')
def test_standalone_bson():
    """Handle different method names for standalone bson codec vs pymongo"""
    import requests_cache.serializers.preconf

    # Can't easily install both pymongo and bson (standalone) for tests;
    # Using json module here since it has same functions as bson (standalone)
    with patch.dict(sys.modules, {'bson': json, 'pymongo': None}):
        reload(requests_cache.serializers.preconf)
        bson_functions = requests_cache.serializers.preconf._get_bson_functions()

        assert bson_functions == {'dumps': 'dumps', 'loads': 'loads'}

    reload(requests_cache.serializers.preconf)


def test_optional_dependencies():
    import requests_cache.serializers.preconf

    with patch.dict(sys.modules, {'bson': None, 'itsdangerous': None, 'yaml': None}):
        reload(requests_cache.serializers.preconf)

        from requests_cache.serializers.preconf import (
            bson_serializer,
            safe_pickle_serializer,
            yaml_serializer,
        )

        for obj in [bson_serializer, yaml_serializer]:
            with pytest.raises(ImportError):
                obj.dumps('')
            with pytest.raises(ImportError):
                obj.loads('')

        with pytest.raises(ImportError):
            safe_pickle_serializer('')

    reload(requests_cache.serializers.preconf)


@skip_missing_deps('itsdangerous')
def test_cache_signing(tempfile_path):
    from itsdangerous import Signer
    from itsdangerous.exc import BadSignature

    serializer = safe_pickle_serializer(secret_key=str(uuid4()))
    session = CachedSession(tempfile_path, serializer=serializer)
    assert isinstance(session.cache.responses.serializer.stages[-1].obj, Signer)

    # Simple serialize/deserialize round trip
    response = CachedResponse()
    session.cache.responses['key'] = response
    assert session.cache.responses['key'] == response

    # Without the same signing key, the item shouldn't be considered safe to deserialize
    serializer = safe_pickle_serializer(secret_key='a different key')
    session = CachedSession(tempfile_path, serializer=serializer)
    with pytest.raises(BadSignature):
        session.cache.responses['key']


def test_custom_serializer(tempfile_path):
    serializer = SerializerPipeline(
        [
            json_serializer,  # Serialize to a JSON string
            utf8_encoder,  # Encode to bytes
            Stage(dumps=gzip.compress, loads=gzip.decompress),  # Compress
        ]
    )
    session = CachedSession(tempfile_path, serializer=serializer)
    response = CachedResponse()
    session.cache.responses['key'] = response
    assert session.cache.responses['key'] == response


def test_plain_pickle(tempfile_path):
    """`requests.Response` modifies pickling behavior. If plain `pickle` is used as a serializer,
    serializing `CachedResponse` should still work as expected.
    """
    session = CachedSession(tempfile_path, serializer=pickle)

    response = CachedResponse()
    session.cache.responses['key'] = response
    assert session.cache.responses['key'] == response
    assert session.cache.responses['key'].expires is None


def test_cattrs_compat():
    """CattrStage should be compatible with BaseConverter, which doesn't support the omit_if_default
    keyword arg.
    """
    stage_1 = CattrStage()
    assert isinstance(stage_1.converter, GenConverter)

    stage_2 = CattrStage(factory=BaseConverter)
    assert isinstance(stage_2.converter, BaseConverter)
