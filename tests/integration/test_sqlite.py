import os
from tempfile import gettempdir
from threading import Thread
from unittest.mock import patch

from requests_cache.backends.sqlite import DbCache, DbDict, DbPickleDict
from tests.integration.base_cache_test import BaseCacheTest
from tests.integration.base_storage_test import CACHE_NAME, BaseStorageTest


class SQLiteTestCase(BaseStorageTest):
    init_kwargs = {'use_temp': True}

    @classmethod
    def teardown_class(cls):
        try:
            os.unlink(f'{CACHE_NAME}.sqlite')
        except Exception:
            pass

    def test_use_temp(self):
        relative_path = self.storage_class(CACHE_NAME).db_path
        temp_path = self.storage_class(CACHE_NAME, use_temp=True).db_path
        assert not relative_path.startswith(gettempdir())
        assert temp_path.startswith(gettempdir())

    def test_bulk_commit(self):
        cache = self.init_cache()
        with cache.bulk_commit():
            pass

        n_items = 1000
        with cache.bulk_commit():
            for i in range(n_items):
                cache[f'key_{i}'] = f'value_{i}'
        assert set(cache.keys()) == {f'key_{i}' for i in range(n_items)}
        assert set(cache.values()) == {f'value_{i}' for i in range(n_items)}

    def test_chunked_bulk_delete(self):
        """When deleting more items than SQLite can handle in a single statement, it should be
        chunked into multiple smaller statements
        """
        # Populate the cache with more items than can fit in a single delete statement
        cache = self.init_cache()
        with cache.bulk_commit():
            for i in range(2000):
                cache[f'key_{i}'] = f'value_{i}'

        keys = list(cache.keys())

        # First pass to ensure that bulk_delete is split across three statements
        with patch.object(cache, 'connection') as mock_connection:
            con = mock_connection().__enter__.return_value
            cache.bulk_delete(keys)
            assert con.execute.call_count == 3

        # Second pass to actually delete keys and make sure it doesn't explode
        cache.bulk_delete(keys)
        assert len(cache) == 0

    def test_switch_commit(self):
        cache = self.init_cache()
        cache.clear()
        cache['key_1'] = 'value_1'
        cache = self.init_cache(clear=False)
        assert 'key_1' in cache

        cache._can_commit = False
        cache['key_2'] = 'value_2'

        cache = self.init_cache(clear=False)
        assert 2 not in cache
        assert cache._can_commit is True

    def test_fast_save(self):
        cache_1 = self.init_cache(1, fast_save=True)
        cache_2 = self.init_cache(2, fast_save=True)

        n = 1000
        for i in range(n):
            cache_1[i] = i
            cache_2[i * 2] = i

        assert set(cache_1.keys()) == set(range(n))
        assert set(cache_2.values()) == set(range(n))

    def test_noop(self):
        def do_noop_bulk(cache):
            with cache.bulk_commit():
                pass
            del cache

        cache = self.init_cache()
        thread = Thread(target=do_noop_bulk, args=(cache,))
        thread.start()
        thread.join()

        # make sure connection is not closed by the thread
        cache['key_1'] = 'value_1'
        assert list(cache.keys()) == ['key_1']

    @patch('requests_cache.backends.sqlite.sqlite3')
    def test_connection_kwargs(self, mock_sqlite):
        """A spot check to make sure optional connection kwargs gets passed to connection"""
        cache = self.storage_class('test', use_temp=True, timeout=0.5, invalid_kwarg='???')
        mock_sqlite.connect.assert_called_with(cache.db_path, timeout=0.5)


class TestDbDict(SQLiteTestCase):
    storage_class = DbDict


class TestDbPickleDict(SQLiteTestCase):
    storage_class = DbPickleDict
    picklable = True


class TestDbCache(BaseCacheTest):
    backend_class = DbCache
    init_kwargs = {'use_temp': True}

    @classmethod
    def teardown_class(cls):
        try:
            os.unlink(CACHE_NAME)
        except Exception:
            pass
