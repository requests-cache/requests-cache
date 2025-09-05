import os
from time import sleep

import pytest

from requests_cache.backends.lru import LRUDict
from tests.conftest import CACHE_NAME


class TestLRUDict:
    def init_cache(self, **kwargs):
        cache = LRUDict(CACHE_NAME, table_name='lru', use_temp=True, **kwargs)
        cache.clear()
        return cache

    @classmethod
    def teardown_class(cls):
        try:
            os.unlink(f'{CACHE_NAME}.sqlite')
        except Exception:
            pass

    def test_get_set(self):
        cache = self.init_cache()
        cache['key1'] = 100
        cache['key2'] = 200
        cache['key3'] = 300
        assert cache['key1'] == 100
        assert cache['key2'] == 200
        assert cache['key3'] == 300

        with pytest.raises(KeyError):
            _ = cache['nonexistent']

    def test_delete(self):
        cache = self.init_cache()
        cache['key'] = 0

        del cache['key']
        with pytest.raises(KeyError):
            _ = cache['key']

    def test_count(self):
        cache = self.init_cache()
        assert cache.count() == 0

        cache['key1'] = 100
        assert cache.count() == 1

        cache['key2'] = 200
        cache['key3'] = 300
        assert cache.count() == 3

        del cache['key1']
        assert cache.count() == 2

    def test_clear(self):
        cache = self.init_cache()
        cache['key1'] = 100
        cache['key2'] = 200
        cache['key3'] = 300
        assert len(cache) == 3
        assert cache.total_size() == 600

        cache.clear()
        assert len(cache) == 0
        assert cache.total_size() == 0

    def test_get_lru(self):
        cache = self.init_cache()
        assert cache.get_lru(total_size=1) == []

        cache['key0'] = 0
        cache['key1'] = 100
        cache['key2'] = 200
        cache['key3'] = 300
        sleep(0.001)
        cache.update_access_time('key1')

        # Order should be (from least to most recent): key0, key2, key3, key1
        assert cache.get_lru(total_size=1) == ['key0', 'key2']
        assert cache.get_lru(total_size=200) == ['key0', 'key2']
        assert cache.get_lru(total_size=201) == ['key0', 'key2', 'key3']
        assert cache.get_lru(total_size=500) == ['key0', 'key2', 'key3']
        assert cache.get_lru(total_size=501) == ['key0', 'key2', 'key3', 'key1']
        assert cache.get_lru(total_size=600) == ['key0', 'key2', 'key3', 'key1']
        assert cache.get_lru(total_size=700) == ['key0', 'key2', 'key3', 'key1']

    def test_total_size(self):
        """Test that total cache size is tracked correctly"""
        cache = self.init_cache()
        assert cache.total_size() == 0

        # Create
        cache['key1'] = 100
        assert cache.total_size() == 100
        cache['key2'] = 200
        assert cache.total_size() == 300

        # Update
        cache['key1'] = 150
        assert cache.total_size() == 350

        # Delete
        del cache['key1']
        assert cache.total_size() == 200

    def test_update_access_time(self):
        cache = self.init_cache()
        cache['key1'] = 100
        cache['key2'] = 200
        cache['key3'] = 300
        assert list(cache.sorted()) == ['key1', 'key2', 'key3']

        sleep(0.001)
        cache.update_access_time('key1')
        assert list(cache.sorted()) == ['key2', 'key3', 'key1']

    def test_update_access_time__keyerror(self):
        cache = self.init_cache()
        with pytest.raises(KeyError):
            cache.update_access_time('nonexistent')
