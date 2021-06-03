"""A manual test to compare performance of different serializers"""
# flake8: noqa: F401
"""
CPU Results:
jsonpickle.encode x10000:     5.673
jsonpickle.decode x10000:     5.448
pickle.dumps x10000:          0.256
pickle.loads x10000:          0.260
cattrs.unstructure x10000:    0.002
cattrs.structure x10000:      0.002
cattrs + pickle.dumps x10000: 0.251
cattrs + pickle.loads x10000: 0.253
"""
import pickle
from time import perf_counter as time

import jsonpickle
from memory_profiler import profile
from rich import print

from requests_cache import CachedSession
from requests_cache.serializers import PickleSerializer

ITERATIONS = 10000

session = CachedSession()
session.cache.clear()
r = session.get('https://httpbin.org/get?x=y')


def test_jsonpickle():
    start = time()
    serialized = [jsonpickle.encode(r, use_base85=True) for i in range(ITERATIONS)]
    print(f'jsonpickle.encode x{ITERATIONS}: {time() - start:.3f}')

    start = time()
    deserialized = [jsonpickle.decode(obj) for obj in serialized]
    print(f'jsonpickle.decode x{ITERATIONS}: {time() - start:.3f}')


def test_pickle():
    start = time()
    serialized = [pickle.dumps(r) for i in range(ITERATIONS)]
    print(f'pickle.dumps x{ITERATIONS}: {time() - start:.3f}')

    start = time()
    serialized = [pickle.dumps(r) for i in range(ITERATIONS)]
    print(f'pickle.loads x{ITERATIONS}: {time() - start:.3f}')


def test_cattrs():
    s = PickleSerializer()
    start = time()
    serialized = [s.unstructure(r) for i in range(ITERATIONS)]
    print(f'cattrs.unstructure x{ITERATIONS}: {time() - start:.3f}')

    start = time()
    deserialized = [s.structure(obj) for obj in serialized]
    print(f'cattrs.structure x{ITERATIONS}: {time() - start:.3f}')


def test_cattrs_pickle():
    s = PickleSerializer()
    start = time()
    serialized = [s.dumps(r) for i in range(ITERATIONS)]
    print(f'cattrs + pickle.dumps x{ITERATIONS}: {time() - start:.3f}')

    start = time()
    deserialized = [s.loads(obj) for obj in serialized]
    print(f'cattrs + pickle.loads x{ITERATIONS}: {time() - start:.3f}')


if __name__ == '__main__':
    print('CPU:')
    test_jsonpickle()
    test_pickle()
    test_cattrs()
    test_cattrs_pickle()

    # Memory
    # print('\nMemory:')
    # profile(test_jsonpickle)()
    # profile(test_pickle)()
    # profile(test_cattrs)()
    # profile(test_cattrs_pickle)()
