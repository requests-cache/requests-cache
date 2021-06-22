# Note: Almost all serializer logic is covered by parametrized integration tests.
# Any additional serializer-specific tests can go here.
import json
import pytest
import sys
from importlib import reload
from unittest.mock import patch

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 7), reason='Requires python 3.7+ version of cattrs'
)


@patch.dict(sys.modules, {'ujson': None, 'cattr.preconf.ujson': None})
def test_stdlib_json():
    import requests_cache.serializers.preconf

    reload(requests_cache.serializers.preconf)
    from requests_cache.serializers.preconf import json as module_json

    assert module_json is json


def test_ujson():
    import ujson

    import requests_cache.serializers.preconf

    reload(requests_cache.serializers.preconf)
    from requests_cache.serializers.preconf import json as module_json

    assert module_json is ujson
