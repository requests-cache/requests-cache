"""Common tests to run for all backends (BaseStorage subclasses)"""
from typing import Dict, Type

import pytest

from requests_cache.backends import BaseStorage
from tests.conftest import CACHE_NAME


# TODO: Parameterize tests for all serializers?
class BaseStorageTest:
    """Base class for testing cache storage dict-like interfaces"""

    storage_class: Type[BaseStorage] = None
    init_kwargs: Dict = {}
    picklable: bool = False
    num_instances: int = 10  # Max number of cache instances to test

    def init_cache(self, cache_name=CACHE_NAME, index=0, clear=True, **kwargs):
        kwargs.setdefault('serializer', 'pickle')
        cache = self.storage_class(cache_name, f'table_{index}', **self.init_kwargs, **kwargs)
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
            cache[f'key_{i}'] == f'value_{i}'
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
