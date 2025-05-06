import json
from requests_cache.cache_keys import normalize_json_body


def test_ignores_nested():
    original = b'{"data":{"key":"value","timestamp":"2022-08-04"}}'
    # Only work for timestamp under data subtree
    result = normalize_json_body(
        original,
        ignored_parameters=['timestamp'],
        content_root_key='data',
    )
    body = json.loads(result)
    assert body == {'data': {'key': 'value', 'timestamp': 'REDACTED'}}


def test_ignores_nested_specialcase():
    original = b'{"data":{"foo":"bar"},"extra":"keep"}'
    result = normalize_json_body(
        original,
        ignored_parameters=['timestamp'],
        content_root_key='data',
    )
    body = json.loads(result)
    # No timestamp under data, should be no filter
    assert body == {'data': {'foo': 'bar'}, 'extra': 'keep'}
