#!/usr/bin/env python3
"""A manual test to compare performance of different serializers

Latest results:
---------------
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
cattrs+bson.dumps: 1.550
cattrs+bson.loads: 1.322
"""
# flake8: noqa: F401
import json
import os
import pickle
import sys
from os.path import abspath, dirname, join
from time import perf_counter as time

import ujson
from cattr.preconf.json import make_converter

try:
    from rich import print
except ImportError:
    pass

# import jsonpickle
# from memory_profiler import profile

# Add project path
sys.path.insert(0, os.path.abspath('..'))

from requests_cache import CachedSession
from requests_cache.serializers import CattrStage, bson_serializer, json_serializer, pickle_serializer

ITERATIONS = 10000

session = CachedSession()
r = session.get('https://httpbin.org/get?x=y')
r = session.get('https://httpbin.org/get?x=y')


# def run_jsonpickle():
#     run_serialize_deserialize('jsonpickle', jsonpickle.encode, jsonpickle.decode)


def run_pickle():
    run_serialize_deserialize('pickle', pickle)


def run_cattrs():
    run_serialize_deserialize('cattrs', CattrStage)


def run_cattrs_pickle():
    run_serialize_deserialize('cattrs+pickle', pickle_serializer)


# def run_cattrs_json():
#     s = CattrStage(converter_factory=make_converter)
#     run_serialize_deserialize(
#         'cattrs+json',
#         lambda obj: json.dumps(s.unstructure(obj)),
#         lambda obj: s.structure(json.loads(obj)),
#     )


def run_cattrs_ujson():
    s = CattrStage(converter_factory=make_converter)
    run_serialize_deserialize('cattrs+ujson', json_serializer)


def run_cattrs_bson():
    run_serialize_deserialize('cattrs+bson', bson_serializer)


def run_serialize_deserialize(module, serializer):
    start = time()
    serialized = [serializer.dumps(r) for i in range(ITERATIONS)]
    print(f'{module}.{serializer.__name__}.loads() x{ITERATIONS}: {time() - start:.3f}')

    start = time()
    deserialized = [serializer.loads(obj) for obj in serialized]
    print(f'{module}.{serializer.__name__}.dumps() x{ITERATIONS}: {time() - start:.3f}')


if __name__ == '__main__':
    print('CPU:')
    # run_jsonpickle()
    run_pickle()
    run_cattrs()
    run_cattrs_pickle()
    # run_cattrs_json()
    run_cattrs_ujson()
    run_cattrs_bson()

    # Memory
    # print('\nMemory:')
    # profile(run_jsonpickle)()
    # profile(run_pickle)()
    # profile(run_cattrs)()
    # profile(run_cattrs_pickle)()
