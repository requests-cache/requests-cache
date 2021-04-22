import pytest
from threading import Thread
from time import time
from typing import Dict, Type

from requests_cache.backends.base import BaseCache, BaseStorage
from requests_cache.session import CachedSession
from tests.conftest import CACHE_NAME, N_ITERATIONS, N_THREADS, httpbin


class BaseStorageTest:
    """Base class for testing cache storage dict-like interfaces"""

    storage_class: Type[BaseStorage] = None
    init_kwargs: Dict = {}
    picklable: bool = False
    num_instances: int = 10  # Max number of cache instances to test

    def init_cache(self, index=0, clear=True, **kwargs):
        kwargs['suppress_warnings'] = True
        cache = self.storage_class(CACHE_NAME, f'table_{index}', **self.init_kwargs, **kwargs)
        if clear:
            cache.clear()
        return cache

    def tearDown(self):
        for i in range(self.num_instances):
            self.init_cache(i, clear=True)
        super().tearDown()

    def test_basic_methods(self):
        """Test basic dict methods with multiple cache instances:
        ``getitem, setitem, delitem, len, contains``
        """
        caches = [self.init_cache(i) for i in range(10)]
        for i in range(self.num_instances):
            caches[i][f'key_{i}'] = f'value_{i}'
            caches[i][f'key_{i+1}'] = f'value_{i+1}'

        for i in range(self.num_instances):
            cache = caches[i]
            cache[f'key_{i}'] == f'value_{i}'
            assert len(cache) == 2
            assert f'key_{i}' in cache and f'key_{i+1}' in cache

            del cache[f'key_{i}']
            assert f'key_{i}' not in cache

    def test_iterable_methods(self):
        """Test iterable dict methods with multiple cache instances:
        ``iter, keys, values, items``
        """
        caches = [self.init_cache(i) for i in range(self.num_instances)]
        for i in range(self.num_instances):
            caches[i][f'key_{i}'] = f'value_{i}'

        for i in range(self.num_instances):
            cache = caches[i]
            assert list(cache) == [f'key_{i}']
            assert list(cache.keys()) == [f'key_{i}']
            assert list(cache.values()) == [f'value_{i}']
            assert list(cache.items()) == [(f'key_{i}', f'value_{i}')]
            assert dict(cache) == {f'key_{i}': f'value_{i}'}

    def test_del(self):
        """Some more tests to ensure ``delitem`` deletes only the expected items"""
        cache = self.init_cache()
        for i in range(20):
            cache[f'key_{i}'] = f'value_{i}'
        for i in range(5):
            del cache[f'key_{i}']

        assert len(cache) == 15
        assert set(cache.keys()) == {f'key_{i}' for i in range(5, 20)}
        assert set(cache.values()) == {f'value_{i}' for i in range(5, 20)}

    def test_keyerrors(self):
        """Accessing or deleting a deleted item should raise a KeyError"""
        cache = self.init_cache()
        cache['key'] = 'value'
        del cache['key']

        with pytest.raises(KeyError):
            del cache['key']
        with pytest.raises(KeyError):
            cache['key']

    def test_picklable_dict(self):
        if self.picklable:
            cache = self.init_cache()
            cache['key_1'] = Picklable()
            assert cache['key_1'].attr_1 == 'value_1'
            assert cache['key_1'].attr_2 == 'value_2'

    def test_clear_and_work_again(self):
        cache_1 = self.init_cache()
        cache_2 = self.init_cache(connection=getattr(cache_1, 'connection', None))

        for i in range(5):
            cache_1[i] = i
            cache_2[i] = i

        assert len(cache_1) == len(cache_2) == 5
        cache_1.clear()
        cache_2.clear()
        assert len(cache_1) == len(cache_2) == 0

    def test_same_settings(self):
        cache_1 = self.init_cache()
        cache_2 = self.init_cache(connection=getattr(cache_1, 'connection', None))
        cache_1['key_1'] = 1
        cache_2['key_2'] = 2
        assert cache_1 == cache_2

    def test_str(self):
        """Not much to test for __str__ methods, just make sure they return keys in some format"""
        cache = self.init_cache()
        for i in range(10):
            cache[f'key_{i}'] = f'value_{i}'
        for i in range(10):
            assert f'key_{i}' in str(cache)


class Picklable:
    attr_1 = 'value_1'
    attr_2 = 'value_2'


class BaseCacheTest:
    """Base class for testing cache backend classes"""

    backend_class: Type[BaseCache] = None
    init_kwargs: Dict = {}

    def init_backend(self, clear=True, **kwargs):
        kwargs['suppress_warnings'] = True
        backend = self.backend_class(CACHE_NAME, **self.init_kwargs, **kwargs)
        if clear:
            backend.redirects.clear()
            backend.responses.clear()
        return backend

    @pytest.mark.parametrize('iteration', range(N_ITERATIONS))
    def test_caching_with_threads(self, iteration):
        """Run a multi-threaded stress test for each backend"""
        start = time()
        session = CachedSession(backend=self.init_backend())
        url = httpbin('anything')

        def send_requests():
            for i in range(N_ITERATIONS):
                session.get(url, params={f'key_{i}': f'value_{i}'})

        threads = [Thread(target=send_requests) for i in range(N_THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        elapsed = time() - start
        average = (elapsed * 1000) / (N_ITERATIONS * N_THREADS)
        print(f'{self.backend_class}: Ran {N_ITERATIONS} iterations with {N_THREADS} threads each in {elapsed} s')
        print(f'Average time per request: {average} ms')

        for i in range(N_ITERATIONS):
            assert session.cache.has_url(f'{url}?key_{i}=value_{i}')
