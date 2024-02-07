"""Common tests to run for all backends (BaseStorage subclasses)"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Dict, Type

import pytest
from attrs import define, field

from requests_cache.backends import BaseStorage
from requests_cache.models import CachedResponse
from tests.conftest import (
    CACHE_NAME,
    N_ITERATIONS,
    N_REQUESTS_PER_ITERATION,
    N_WORKERS,
)


class BaseStorageTest:
    """Base class for testing cache storage dict-like interfaces"""

    storage_class: Type[BaseStorage] = None
    init_kwargs: Dict = {}
    num_instances: int = 10  # Max number of cache instances to test

    def init_cache(self, cache_name=CACHE_NAME, index=0, clear=True, **kwargs):
        kwargs = {**self.init_kwargs, **kwargs}
        cache = self.storage_class(cache_name, f'table_{index}', **kwargs)
        if clear:
            cache.clear()
        return cache

    def teardown_class(cls):
        for i in range(cls.num_instances):
            cls().init_cache(index=i, clear=True)

    def test_basic_methods(self):
        """Test basic dict methods with multiple cache instances:
        ``getitem, setitem, delitem, len, contains``
        """
        caches = [self.init_cache(index=i) for i in range(10)]
        for i in range(self.num_instances):
            cached_response = CachedResponse()
            cached_response._content = str(i).encode()
            caches[i][f'key_{i}'] = cached_response

            cached_response = CachedResponse()
            cached_response._content = str(i + 1).encode()
            caches[i][f'key_{i+1}'] = cached_response

            cache = caches[i]
            assert cache[f'key_{i}']._content == str(i).encode()
            assert len(cache) == 2
            assert f'key_{i}' in cache and f'key_{i+1}' in cache

            del cache[f'key_{i}']
            assert f'key_{i}' not in cache

    def test_iterable_methods(self):
        """Test iterable dict methods with multiple cache instances:
        ``iter, keys, values, items``
        """
        caches = [self.init_cache(index=i) for i in range(self.num_instances)]
        for i in range(self.num_instances):
            cached_response = CachedResponse()
            cached_response._content = str(i).encode()
            caches[i][f'key_{i}'] = cached_response

        for i in range(self.num_instances):
            cache = caches[i]
            assert list(cache) == [f'key_{i}']
            assert list(cache.keys()) == [f'key_{i}']
            cached_response = CachedResponse()
            cached_response._content = str(i).encode()
            assert list(cache.values())[0]._content == cached_response._content
            assert list(cache.items())[0][1]._content == cached_response._content
            assert dict(cache)[f'key_{i}']._content == cached_response._content

    def test_cache_key(self):
        """The cache_key attribute should be available on responses returned from all
        mapping/collection methods
        """
        cache = self.init_cache()
        cache['key'] = CachedResponse()
        assert cache['key'].cache_key == 'key'
        assert list(cache.values())[0].cache_key == 'key'
        assert list(cache.items())[0][1].cache_key == 'key'

    def test_del(self):
        """Some more tests to ensure ``delitem`` deletes only the expected items"""
        cache = self.init_cache()
        for i in range(20):
            cached_response = CachedResponse()
            cached_response._content = str(i).encode()
            cache[f'key_{i}'] = cached_response
        for i in range(5):
            del cache[f'key_{i}']

        assert len(cache) == 15
        assert set(cache.keys()) == {f'key_{i}' for i in range(5, 20)}
        assert len(list(cache.values())) == 15
        assert all(cache[f'key_{i}']._content == str(i).encode() for i in range(5, 20))

    def test_bulk_delete(self):
        cache = self.init_cache()
        for i in range(20):
            cached_response = CachedResponse()
            cached_response._content = str(i).encode()
            cache[f'key_{i}'] = cached_response
        cache.bulk_delete([f'key_{i}' for i in range(5)])
        cache.bulk_delete(['nonexistent_key'])

        assert len(cache) == 15
        assert set(cache.keys()) == {f'key_{i}' for i in range(5, 20)}
        assert all(cache[f'key_{i}']._content == str(i).encode() for i in range(5, 20))

    def test_bulk_delete__noop(self):
        """Just make sure bulk_delete doesn't do anything unexpected if no keys are provided"""
        cache = self.init_cache()
        for i in range(20):
            cache[f'key_{i}'] = f'value_{i}'
        cache.bulk_delete([])
        assert len(cache) == 20

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
        cache = self.init_cache(serializer='pickle')
        original_obj = CachedResponse(created_at=datetime.now(timezone.utc))
        cache['key_1'] = original_obj

        obj = cache['key_1']
        assert obj == original_obj
        assert obj.created_at == original_obj.created_at

    def test_clear_and_work_again(self):
        cache_1 = self.init_cache()
        cache_2 = self.init_cache(connection=getattr(cache_1, 'connection', None))

        for i in range(5):
            cache_1[f'key_{i}'] = f'value_{i}'
            cache_2[f'key_{i}'] = f'value_{i}'

        assert len(cache_1) == len(cache_2) == 5
        cache_1.clear()
        cache_2.clear()
        assert len(cache_1) == len(cache_2) == 0

    def test_same_settings(self):
        cache_1 = self.init_cache()
        cache_2 = self.init_cache(connection=getattr(cache_1, 'connection', None))
        assert cache_1 == cache_2
        cache_1['key_1'] = 'value_1'
        cache_2['key_2'] = 'value_2'
        assert cache_1 != cache_2

    def test_str(self):
        """Not much to test for __str__ methods, just make sure they return keys in some format"""
        cache = self.init_cache()
        for i in range(10):
            cache[f'key_{i}'] = f'value_{i}'
        for i in range(10):
            assert f'key_{i}' in str(cache)

    def test_concurrency(self):
        """Test a large number of concurrent write operations for each backend"""
        cache = self.init_cache()

        def write(i):
            cache[f'key_{i}'] = f'value_{i}'

        n_iterations = N_ITERATIONS * N_REQUESTS_PER_ITERATION * 10
        with ThreadPoolExecutor(max_workers=N_WORKERS * 2) as executor:
            _ = list(executor.map(write, range(n_iterations)))


@define
class BasicDataclass:
    bool_attr: bool = field(default=None)
    datetime_attr: datetime = field(default=None)
    int_attr: int = field(default=None)
    str_attr: str = field(default=None)
