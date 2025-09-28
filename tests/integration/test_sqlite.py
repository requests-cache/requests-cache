import os
import pickle
import sqlite3
from datetime import timedelta
from os.path import join
from tempfile import NamedTemporaryFile, gettempdir
from threading import Thread
from time import sleep
from unittest.mock import patch

import pytest
from platformdirs import user_cache_dir

from requests_cache.backends import BaseCache, LRUSQLiteDict, SQLiteCache, SQLiteDict
from requests_cache.backends.sqlite import MEMORY_URI
from requests_cache.models import CachedResponse
from requests_cache.policy import utcnow
from requests_cache.serializers import utf8_serializer
from tests.conftest import skip_pypy
from tests.integration.base_cache_test import BaseCacheTest
from tests.integration.base_storage_test import CACHE_NAME, BaseStorageTest


class TestSQLiteDict(BaseStorageTest):
    storage_class = SQLiteDict
    init_kwargs = {'use_temp': True}

    @classmethod
    def teardown_class(cls):
        try:
            os.unlink(f'{CACHE_NAME}.sqlite')
        except Exception:
            pass

    @patch('requests_cache.backends.sqlite.sqlite3')
    def test_connection_kwargs(self, mock_sqlite):
        """A spot check to make sure optional connection kwargs gets passed to connection;
        except for isolation_level, which is ignored
        """
        cache = self.storage_class(
            'test', use_temp=True, timeout=0.5, isolation_level='DEFERRED', invalid_kwarg='???'
        )
        mock_sqlite.connect.assert_called_with(
            cache.db_path, timeout=0.5, isolation_level=None, check_same_thread=False
        )

    def test_use_cache_dir(self):
        relative_path = self.storage_class(CACHE_NAME).db_path
        cache_dir_path = self.storage_class(CACHE_NAME, use_cache_dir=True).db_path
        assert not str(relative_path).startswith(user_cache_dir())
        assert str(cache_dir_path).startswith(user_cache_dir())

    def test_use_temp(self):
        relative_path = self.storage_class(CACHE_NAME).db_path
        temp_path = self.storage_class(CACHE_NAME, use_temp=True).db_path
        assert not str(relative_path).startswith(gettempdir())
        assert str(temp_path).startswith(gettempdir())

    def test_use_memory(self):
        cache = self.init_cache(use_memory=True)
        assert cache.db_path == MEMORY_URI
        for i in range(20):
            cache[f'key_{i}'] = f'value_{i}'
        for i in range(5):
            del cache[f'key_{i}']

        assert len(cache) == 15
        assert set(cache.keys()) == {f'key_{i}' for i in range(5, 20)}
        assert set(cache.values()) == {f'value_{i}' for i in range(5, 20)}

        cache.clear()
        assert len(cache) == 0

    def test_use_memory__uri(self):
        assert self.init_cache(':memory:').db_path == ':memory:'

    def test_non_dir_parent_exists(self):
        """Expect a custom error message if a parent path already exists but isn't a directory"""
        with NamedTemporaryFile() as tmp:
            with pytest.raises(FileExistsError) as exc_info:
                self.storage_class(join(tmp.name, 'invalid_path'))
                assert 'not a directory' in str(exc_info.value)

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

    def test_bulk_delete__chunked(self):
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

    def test_bulk_commit__noop(self):
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

    @skip_pypy
    @pytest.mark.parametrize('kwargs', [{'busy_timeout': 5}, {'fast_save': True}, {'wal': True}])
    def test_pragma(self, kwargs):
        """Test settings that make additional PRAGMA statements"""
        cache_1 = self.init_cache('cache_1', **kwargs)
        cache_2 = self.init_cache('cache_2', **kwargs)

        n = 500
        for i in range(n):
            cache_1[f'key_{i}'] = f'value_{i}'
            cache_2[f'key_{i * 2}'] = f'value_{i}'

        assert set(cache_1.keys()) == {f'key_{i}' for i in range(n)}
        assert set(cache_2.values()) == {f'value_{i}' for i in range(n)}

    def test_busy_timeout(self):
        cache = self.init_cache(busy_timeout=5)
        with cache.connection() as con:
            r = con.execute('PRAGMA busy_timeout').fetchone()
            assert r[0] == 5

    def test_wal_sync_mode(self):
        # Should default to 'NORMAL' (1)
        cache = self.init_cache(wal=True)
        with cache.connection() as con:
            r = con.execute('PRAGMA synchronous').fetchone()
            assert r[0] == 1

        # Not recommended, but should still work
        cache = self.init_cache(wal=True, fast_save=True)
        with cache.connection() as con:
            r = con.execute('PRAGMA synchronous').fetchone()
            assert r[0] == 0

    def test_write_acquire_lock(self):
        """Writes to the database acquire the sqlite lock"""
        cache = self.init_cache()
        with patch.object(cache, '_acquire_sqlite_lock') as mock_write:
            cache['key_1'] = 'value_1'
            assert mock_write.call_count == 1

    def test_write_retry_acquire_lock(self):
        """Acquiring the lock should retry until it succeeds"""
        cache = self.init_cache()
        with patch.object(cache, '_connection') as mock_connection:
            mock_connection.execute.side_effect = [sqlite3.OperationalError] * 10 + [None]
            with cache._acquire_sqlite_lock():
                pass
            assert mock_connection.execute.call_count == 11

    @skip_pypy
    @pytest.mark.parametrize('limit', [None, 50])
    def test_sorted__by_size(self, limit):
        cache = self.init_cache()

        # Insert items with decreasing size
        for i in range(100):
            suffix = 'padding' * (100 - i)
            cache[f'key_{i}'] = f'value_{i}_{suffix}'

        # Sorted items should be in ascending order by size
        items = list(cache.sorted(key='size'))
        assert len(items) == limit or 100

        prev_item = None
        for item in items:
            assert prev_item is None or len(prev_item) > len(item)

    @skip_pypy
    def test_sorted__reversed(self):
        cache = self.init_cache()

        for i in range(100):
            cache[f'key_{i + 1:03}'] = f'value_{i + 1}'

        items = list(cache.sorted(key='key', reversed=True))
        assert len(items) == 100
        for i, item in enumerate(items):
            assert item == f'value_{100 - i}'

    @skip_pypy
    def test_sorted__invalid_sort_key(self):
        cache = self.init_cache()
        cache['key_1'] = 'value_1'
        with pytest.raises(ValueError):
            list(cache.sorted(key='invalid_key'))

    @skip_pypy
    @pytest.mark.parametrize('limit', [None, 50])
    def test_sorted__by_expires(self, limit):
        cache = self.init_cache()
        now = utcnow()

        # Insert items with decreasing expiration time
        for i in range(100):
            response = CachedResponse(expires=now + timedelta(seconds=101 - i))
            cache[f'key_{i}'] = response

        # Sorted items should be in ascending order by expiration time
        items = list(cache.sorted(key='expires'))
        assert len(items) == limit or 100

        prev_item = None
        for item in items:
            assert prev_item is None or prev_item.expires < item.expires

    @skip_pypy
    def test_sorted__exclude_expired(self):
        cache = self.init_cache()
        now = utcnow()

        # Make only odd numbered items expired
        for i in range(100):
            delta = 101 - i
            if i % 2 == 1:
                delta -= 101

            response = CachedResponse(status_code=i, expires=now + timedelta(seconds=delta))
            cache[f'key_{i}'] = response

        # Items should only include unexpired (even numbered) items, and still be in sorted order
        items = list(cache.sorted(key='expires', expired=False))
        assert len(items) == 50
        prev_item = None

        for item in items:
            assert prev_item is None or prev_item.expires < item.expires
            assert item.status_code % 2 == 0

    @skip_pypy
    def test_sorted__error(self):
        """sorted() should handle deserialization errors and not return invalid responses"""

        class BadSerializer:
            def loads(self, value):
                response = pickle.loads(value)
                if response.cache_key == 'key_42':
                    raise pickle.PickleError()
                return response

            def dumps(self, value):
                return pickle.dumps(value)

        cache = self.init_cache(serializer=BadSerializer())

        for i in range(100):
            response = CachedResponse(status_code=i)
            response.cache_key = f'key_{i}'
            cache[f'key_{i}'] = response

        # Items should only include unexpired (even numbered) items, and still be in sorted order
        items = list(cache.sorted())
        assert len(items) == 99

    @pytest.mark.parametrize(
        'db_path, use_temp',
        [
            ('filesize_test', True),
            (':memory:', False),
        ],
    )
    def test_size(self, db_path, use_temp):
        """Test approximate expected size of a database, for both file-based and in-memory databases"""
        cache = self.init_cache(db_path, use_temp=use_temp)
        for i in range(100):
            cache[f'key_{i}'] = f'value_{i}'
        assert 10000 < cache.size() < 200000


class TestLRUSQLiteDict(TestSQLiteDict):
    storage_class = LRUSQLiteDict
    init_kwargs = {'use_temp': True, 'max_cache_bytes': 10 * 1024 * 1024}

    def test_get_set_with_lru_tracking(self):
        """Test basic get/set operations with LRU access time tracking."""
        cache = self.init_cache()
        cache['key1'] = 'value1'
        cache['key2'] = 'value2'
        cache['key3'] = 'value3'

        assert cache['key1'] == 'value1'
        assert cache['key2'] == 'value2'
        assert cache['key3'] == 'value3'

        # Check that LRU metadata is stored
        with cache.connection() as con:
            rows = con.execute(
                f'SELECT key, access_time, size FROM {cache.table_name} ORDER BY key'
            ).fetchall()
            assert len(rows) == 3
            for row in rows:
                assert row[1] is not None  # access_time should be set
                assert row[2] > 0  # size should be positive

    def test_access_time_update(self):
        """Test that access times are updated on reads."""
        cache = self.init_cache()
        cache['key1'] = 'value1'
        cache['key2'] = 'value2'

        # Get initial access times
        with cache.connection() as con:
            initial_times = {
                row[0]: row[1]
                for row in con.execute(
                    f'SELECT key, access_time FROM {cache.table_name}'
                ).fetchall()
            }

        sleep(0.001)  # Ensure time difference
        _ = cache['key1']  # This should update access_time for key1

        with cache.connection() as con:
            updated_times = {
                row[0]: row[1]
                for row in con.execute(
                    f'SELECT key, access_time FROM {cache.table_name}'
                ).fetchall()
            }

        assert updated_times['key1'] > initial_times['key1']
        assert updated_times['key2'] == initial_times['key2']

    def test_eviction_on_size_limit(self):
        """Test that items are evicted when cache size limit is reached."""
        cache = self.init_cache(max_cache_bytes=40000, serializer=utf8_serializer)
        cache['key1'] = 'x' * 2000
        sleep(0.001)
        cache['key2'] = 'y' * 2000
        sleep(0.001)
        cache['key3'] = 'z' * 2000

        # key1 should be evicted (least recently used)
        assert 'key1' not in cache
        assert 'key2' in cache
        assert 'key3' in cache

    def test_do_not_store_items_too_big(self):
        """Test that items larger than max_cache_bytes are not stored."""
        cache = self.init_cache(max_cache_bytes=25000, serializer=utf8_serializer)
        large_value = 'x' * 26000

        cache['small_key'] = 'small_value'
        cache['large_key'] = large_value

        assert 'small_key' in cache
        assert 'large_key' not in cache
        assert cache['small_key'] == 'small_value'

    def test_lru_eviction_order(self):
        """Test that eviction follows LRU order."""
        cache = self.init_cache(max_cache_bytes=58000, serializer=utf8_serializer)
        cache['key1'] = 'x' * 2000
        sleep(0.001)
        cache['key2'] = 'x' * 2000
        sleep(0.001)
        cache['key3'] = 'x' * 2000
        sleep(0.001)

        # Make key1 the most recently used
        _ = cache['key1']
        sleep(0.001)

        # Add a new item that should evict key2 (least recently used after key1 access)
        cache['key4'] = 'x' * 2000
        assert 'key1' in cache
        assert 'key2' not in cache
        assert 'key3' in cache
        assert 'key4' in cache

    def test_get_lru(self):
        """Test the get_lru method."""
        cache = self.init_cache(serializer=utf8_serializer)

        cache['key1'] = 'x' * 10
        sleep(0.001)
        cache['key2'] = 'x' * 20
        sleep(0.001)
        cache['key3'] = 'x' * 30

        # Should return keys in LRU order until total size >= requested
        lru_keys = cache.get_lru(25)  # Should get key1 (10) + key2 (20) = 30 >= 25
        assert lru_keys == ['key1', 'key2']

        lru_keys = cache.get_lru(55)  # Should get all keys (10 + 20 + 30 = 60 >= 55)
        assert lru_keys == ['key1', 'key2', 'key3']

        lru_keys = cache.get_lru(5)  # Should get just key1 (10 >= 5)
        assert lru_keys == ['key1']

    def test_update_existing_item(self):
        """Test updating an existing item updates size and access_time."""
        cache = self.init_cache()

        cache['key1'] = 'small'
        original_time = None
        original_size = None

        with cache.connection() as con:
            row = con.execute(
                f'SELECT access_time, size FROM {cache.table_name} WHERE key=?', ('key1',)
            ).fetchone()
            original_time = row[0]
            original_size = row[1]

        sleep(0.001)
        cache['key1'] = 'much_larger_value'

        with cache.connection() as con:
            row = con.execute(
                f'SELECT access_time, size FROM {cache.table_name} WHERE key=?', ('key1',)
            ).fetchone()
            new_time = row[0]
            new_size = row[1]

        assert new_time > original_time
        assert new_size > original_size

    def test_delete_item(self):
        """Test that deleting items works correctly."""
        cache = self.init_cache()

        cache['key1'] = 'value1'
        cache['key2'] = 'value2'

        assert len(cache) == 2
        del cache['key1']
        assert len(cache) == 1
        assert 'key1' not in cache
        assert 'key2' in cache

    def test_multiple_cache_instances(self):
        """Test that multiple cache instances see the same data."""
        cache1 = self.init_cache(index=1)
        cache2 = self.init_cache(index=1, clear=False)

        cache1['key1'] = 'value1'
        assert cache2['key1'] == 'value1'

        del cache1['key1']
        assert 'key1' not in cache2

    def test_bulk_operations_with_eviction(self):
        """Test bulk operations trigger appropriate evictions."""
        cache = self.init_cache(max_cache_bytes=26000, serializer=utf8_serializer)

        with cache.bulk_commit():
            for i in range(20):
                cache[f'key_{i}'] = 'x' * 150

        assert len(cache) < 20
        assert len(cache) > 0

    def test_eviction_with_update(self):
        """Test eviction calculation when updating existing keys."""
        # Use max_cache_bytes that accounts for SQLite database overhead (~24KB minimum)
        cache = self.init_cache(max_cache_bytes=25200, serializer=utf8_serializer)

        cache['key1'] = 'x' * 400
        cache['key2'] = 'x' * 400

        # Update key1 with larger value - should trigger eviction of key2
        cache['key1'] = 'x' * 800
        assert 'key1' in cache
        assert 'key2' not in cache


class TestSQLiteCache(BaseCacheTest):
    backend_class = SQLiteCache
    init_kwargs = {'use_temp': True}

    @classmethod
    def teardown_class(cls):
        try:
            os.unlink(CACHE_NAME)
        except Exception:
            pass

    @patch.object(BaseCache, 'clear', side_effect=IOError)
    @patch('requests_cache.backends.sqlite.unlink', side_effect=os.unlink)
    def test_clear__failure(self, mock_unlink, mock_clear):
        """When a corrupted cache prevents a normal DROP TABLE, clear() should still succeed"""
        session = self.init_session(clear=False)
        session.cache.responses['key_1'] = 'value_1'
        session.cache.clear()

        assert len(session.cache.responses) == 0
        assert mock_unlink.call_count == 1

    @patch.object(BaseCache, 'clear', side_effect=IOError)
    def test_clear__file_already_deleted(self, mock_clear):
        session = self.init_session(clear=False)
        session.cache.responses['key_1'] = 'value_1'
        os.unlink(session.cache.responses.db_path)
        session.cache.clear()

        assert len(session.cache.responses) == 0

    def test_db_path(self):
        """This is just provided as an alias, since both requests and redirects share the same db
        file
        """
        session = self.init_session()
        assert session.cache.db_path == session.cache.responses.db_path

    def test_count(self):
        """count() should work the same as len(), but with the option to exclude expired responses"""
        session = self.init_session()
        now = utcnow()
        session.cache.responses['key_1'] = CachedResponse(expires=now + timedelta(1))
        session.cache.responses['key_2'] = CachedResponse(expires=now - timedelta(1))

        assert session.cache.count() == 2
        assert session.cache.count(expired=False) == 1

    def test_delete__single_key(self):
        """Vacuum should not be used after delete if there is only a single key"""
        session = self.init_session()
        session.cache.responses['key_1'] = 'value_1'

        with patch.object(SQLiteDict, 'vacuum') as mock_vacuum:
            session.cache.delete('key_1')
            mock_vacuum.assert_not_called()

    def test_delete__skip_vacuum(self):
        """Vacuum should not be used after delete if disabled"""
        session = self.init_session()
        session.cache.responses['key_1'] = 'value_1'
        session.cache.responses['key_2'] = 'value_2'

        with patch.object(SQLiteDict, 'vacuum') as mock_vacuum:
            session.cache.delete('key_1', 'key_2', vacuum=False)
            mock_vacuum.assert_not_called()

    @patch.object(SQLiteDict, 'sorted')
    def test_filter__expired(self, mock_sorted):
        """Filtering by expired should use a more efficient SQL query"""
        session = self.init_session()

        session.cache.filter()
        mock_sorted.assert_called_with(expired=True)

        session.cache.filter(expired=False)
        mock_sorted.assert_called_with(expired=False)

    def test_sorted(self):
        """Test wrapper method for SQLiteDict.sorted(), with all arguments combined"""
        session = self.init_session(clear=False)
        now = utcnow()

        # Insert items with decreasing expiration time
        for i in range(500):
            delta = 1000 - i
            if i > 400:
                delta -= 2000

            response = CachedResponse(status_code=i, expires=now + timedelta(seconds=delta))
            session.cache.responses[f'key_{i}'] = response

        # Sorted items should be in ascending order by expiration time
        items = list(session.cache.sorted(key='expires', expired=False, reversed=True, limit=100))
        assert len(items) == 100

        prev_item = None
        for item in items:
            assert prev_item is None or prev_item.expires < item.expires
            assert item.cache_key
            assert not item.is_expired

    # TODO
    def test_drop_oldest_files(self):
        """Check that responses are added up to the max size.

        After adding, the least recently used ones are dropped.
        """

    # TODO
    def test_do_not_store_files_too_big(self, max_size_on_disk):
        """If a file is too big, it should not be cached at all."""
