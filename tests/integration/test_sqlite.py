import os
import unittest
from threading import Thread
from unittest.mock import patch

from requests_cache.backends.sqlite import DbDict, DbPickleDict
from tests.integration.test_backends import CACHE_NAME, BaseStorageTestCase


class SQLiteTestCase(BaseStorageTestCase):
    def tearDown(self):
        try:
            os.unlink(CACHE_NAME)
        except Exception:
            pass

    def test_bulk_commit(self):
        cache = self.init_cache()
        with cache.bulk_commit():
            pass

        n = 1000
        with cache.bulk_commit():
            for i in range(n):
                cache[i] = i
        assert list(cache.keys()) == list(range(n))

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

    def test_usage_with_threads(self):
        def do_test_for(cache, n_threads=5):
            cache.clear()

            def do_inserts(values):
                for v in values:
                    cache[v] = v

            def values(x, n):
                return [i * x for i in range(n)]

            threads = [Thread(target=do_inserts, args=(values(i, n_threads),)) for i in range(n_threads)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            for i in range(n_threads):
                for x in values(i, n_threads):
                    assert cache[x] == x

        do_test_for(self.init_cache())
        do_test_for(self.init_cache(fast_save=True), 20)
        do_test_for(self.init_cache(fast_save=True))
        do_test_for(self.init_cache('table_2', fast_save=True))

    def test_noop(self):
        def do_noop_bulk(d):
            with d.bulk_commit():
                pass
            del d

        cache = self.init_cache()
        thread = Thread(target=do_noop_bulk, args=(cache,))
        thread.start()
        thread.join()

        # make sure connection is not closed by the thread
        cache[0] = 0
        assert str(cache) == "{0: 0}"


class DbDictTestCase(SQLiteTestCase, unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, storage_class=DbDict, **kwargs)


class DbPickleDictTestCase(SQLiteTestCase, unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, storage_class=DbPickleDict, picklable=True, **kwargs)


@patch('requests_cache.backends.sqlite.sqlite3')
def test_connection_kwargs(mock_sqlite):
    """A spot check to make sure optional connection kwargs gets passed to connection"""
    cache = DbDict('test', timeout=0.5, invalid_kwarg='???')
    mock_sqlite.connect.assert_called_with(cache.db_path, timeout=0.5)
