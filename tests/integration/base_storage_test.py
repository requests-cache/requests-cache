"""Common tests to run for all backends (BaseStorage subclasses)"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Type

import pytest
from attrs import define, field

from requests_cache.backends import BaseStorage
from requests_cache.models import CachedResponse
from tests.conftest import CACHE_NAME, N_ITERATIONS, N_REQUESTS_PER_ITERATION, N_WORKERS


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
            caches[i][f'key_{i}'] = f'value_{i}'
            caches[i][f'key_{i+1}'] = f'value_{i+1}'

        for i in range(self.num_instances):
            cache = caches[i]
            assert cache[f'key_{i}'] == f'value_{i}'
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
            caches[i][f'key_{i}'] = f'value_{i}'

        for i in range(self.num_instances):
            cache = caches[i]
            assert list(cache) == [f'key_{i}']
            assert list(cache.keys()) == [f'key_{i}']
            assert list(cache.values()) == [f'value_{i}']
            assert list(cache.items()) == [(f'key_{i}', f'value_{i}')]
            assert dict(cache) == {f'key_{i}': f'value_{i}'}

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
            cache[f'key_{i}'] = f'value_{i}'
        for i in range(5):
            del cache[f'key_{i}']

        assert len(cache) == 15
        assert set(cache.keys()) == {f'key_{i}' for i in range(5, 20)}
        assert set(cache.values()) == {f'value_{i}' for i in range(5, 20)}

    def test_bulk_delete(self):
        cache = self.init_cache()
        for i in range(20):
            cache[f'key_{i}'] = f'value_{i}'
        cache.bulk_delete([f'key_{i}' for i in range(5)])
        cache.bulk_delete(['nonexistent_key'])

        assert len(cache) == 15
        assert set(cache.keys()) == {f'key_{i}' for i in range(5, 20)}
        assert set(cache.values()) == {f'value_{i}' for i in range(5, 20)}

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

    def test_deleting_key_that_does_not_exist_does_not_delete_other_keys(self):
        """If a key does not exist, deleting it should not delete other keys."""
        cache = self.init_cache()
        cache['key'] = 'value'
        with pytest.raises(KeyError):
            del cache['absent']
        assert len(cache) == 1
        assert 'key' in cache

    def test_picklable_dict(self):
        cache = self.init_cache(serializer='pickle')
        original_obj = BasicDataclass(
            bool_attr=True,
            datetime_attr=datetime(2022, 2, 2),
            int_attr=2,
            str_attr='value',
        )
        cache['key_1'] = original_obj

        obj = cache['key_1']
        assert obj.bool_attr == original_obj.bool_attr
        assert obj.datetime_attr == original_obj.datetime_attr
        assert obj.int_attr == original_obj.int_attr
        assert obj.str_attr == original_obj.str_attr

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
        assert not cache_1 and not cache_2
        assert list(cache_1.keys()) == list(cache_2.keys()) == []

    def test_same_settings(self):
        cache_1 = self.init_cache()
        cache_2 = self.init_cache(connection=getattr(cache_1, 'connection', None))
        cache_1['key_1'] = 'value_1'
        cache_2['key_2'] = 'value_2'
        assert cache_1 == cache_2

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

    def test_bool(self):
        """Check boolean conversion."""
        cache = self.init_cache()
        assert not cache
        cache['key'] = 'value'
        assert cache
        del cache['key']
        assert not cache

    def test_reused_keys_can_be_removed(self):
        """Keys can be reused and can be removed."""
        cache = self.init_cache()
        cache['key'] = 'value'
        del cache['key']
        assert list(cache.keys()) == []
        cache['key'] = 'value'
        cache['key2'] = 'value2'
        del cache['key']
        assert list(cache.keys()) == ['key2']
        del cache['key2']
        assert list(cache.keys()) == []

    def test_values_are_replaced(self):
        """Check that keys are added."""
        cache = self.init_cache()
        cache['key'] = 'value'
        assert list(cache.keys()) == ['key']
        cache['key'] = 'value2'
        assert cache['key'] == 'value2'
        assert list(cache.keys()) == ['key']
        cache['key2'] = 'value3'
        assert set(cache.keys()) == {'key', 'key2'}
        assert cache['key'] == 'value2'
        assert cache['key2'] == 'value3'


@define
class BasicDataclass:
    bool_attr: bool = field(default=None)
    datetime_attr: datetime = field(default=None)
    int_attr: int = field(default=None)
    str_attr: str = field(default=None)
