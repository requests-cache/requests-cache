"""A manual test to compare performance of different serializers"""
# flake8: noqa: F401
"""
CPU Results (x10000 iterations):
jsonpickle.encode:      8.846
jsonpickle.decode:      9.166
pickle.dumps:           0.433
pickle.loads:           0.734
cattrs.unstructure:     1.124
cattrs.structure:       1.048
cattrs+pickle.dumps:    1.219
cattrs+pickle.loads:    1.189
cattrs+json.dumps:      2.005
cattrs+json.loads:      2.312
cattrs+ujson.dumps:     1.803
cattrs+ujson.loads:     2.128
"""
import json
import os
import pickle
import sys
from os.path import abspath, dirname, join
from time import perf_counter as time

import jsonpickle
import ujson
from cattr.preconf.json import make_converter
from memory_profiler import profile
from rich import print

# Add project path
sys.path.insert(0, os.path.abspath('..'))

from requests_cache import CachedSession
from requests_cache.serializers import BaseSerializer, JSONSerializer, PickleSerializer

ITERATIONS = 10000

session = CachedSession()
r = session.get('https://httpbin.org/get?x=y')
r = session.get('https://httpbin.org/get?x=y')


def test_jsonpickle():
    base_test('jsonpickle', jsonpickle.encode, jsonpickle.decode)


def test_pickle():
    base_test('pickle', pickle.dumps, pickle.loads)


def test_cattrs():
    s = PickleSerializer()
    base_test('cattrs', s.unstructure, s.structure)


def test_cattrs_pickle():
    s = PickleSerializer()
    base_test('PickleSerializer', s.dumps, s.loads)


def test_cattrs_json():
    s = BaseSerializer(converter_factory=make_converter)
    base_test(
        'json',
        lambda obj: json.dumps(s.unstructure(obj)),
        lambda obj: s.structure(json.loads(obj)),
    )


def test_cattrs_ujson():
    s = BaseSerializer(converter_factory=make_converter)
    base_test(
        'ujson',
        lambda obj: ujson.dumps(s.unstructure(obj)),
        lambda obj: s.structure(ujson.loads(obj)),
    )


def base_test(module, serialize, deserialize):
    start = time()
    serialized = [serialize(r) for i in range(ITERATIONS)]
    print(f'{module}.{serialize.__name__} x{ITERATIONS}: {time() - start:.3f}')

    start = time()
    deserialized = [deserialize(obj) for obj in serialized]
    print(f'{module}.{deserialize.__name__} x{ITERATIONS}: {time() - start:.3f}')


def dumps(self, response: CachedResponse) -> bytes:
    return json.dumps(super().unstructure(response), indent=2)  # , cls=ResponseJSONEncoder)


def loads(self, obj: bytes) -> CachedResponse:
    return super().structure(json.loads(obj))


if __name__ == '__main__':
    print('CPU:')
    # test_jsonpickle()
    test_pickle()
    test_cattrs()
    test_cattrs_pickle()
    test_cattrs_json()
    test_cattrs_ujson()

    # Memory
    # print('\nMemory:')
    # profile(test_jsonpickle)()
    # profile(test_pickle)()
    # profile(test_cattrs)()
    # profile(test_cattrs_pickle)()
