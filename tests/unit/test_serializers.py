# Note: Almost all serializer logic is covered by parametrized integration tests.
# Any additional serializer-specific tests can go here.
import json
import sys
from importlib import reload
from unittest.mock import patch
from uuid import uuid4

import pytest
from itsdangerous import Signer
from itsdangerous.exc import BadSignature

from requests_cache import CachedResponse, CachedSession, safe_pickle_serializer


def test_stdlib_json():
    import requests_cache.serializers.preconf

    with patch.dict(sys.modules, {'ujson': None, 'cattr.preconf.ujson': None}):
        reload(requests_cache.serializers.preconf)
        from requests_cache.serializers.preconf import json as module_json

        assert module_json is json

    reload(requests_cache.serializers.preconf)


def test_ujson():
    import ujson

    from requests_cache.serializers.preconf import json as module_json

    assert module_json is ujson


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
            safe_pickle_serializer('')

    reload(requests_cache.serializers.preconf)


def test_cache_signing(tempfile_path):
    serializer = safe_pickle_serializer(secret_key=str(uuid4()))
    session = CachedSession(tempfile_path, serializer=serializer)
    assert isinstance(session.cache.responses.serializer.steps[-1].obj, Signer)

    # Simple serialize/deserialize round trip
    response = CachedResponse()
    session.cache.responses['key'] = response
    assert session.cache.responses['key'] == response

    # Without the same signing key, the item shouldn't be considered safe to deserialize
    serializer = safe_pickle_serializer(secret_key='a different key')
    session = CachedSession(tempfile_path, serializer=serializer)
    with pytest.raises(BadSignature):
        session.cache.responses['key']
