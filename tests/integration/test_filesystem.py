import os
from shutil import rmtree
from tempfile import gettempdir
from threading import RLock
from time import sleep

import pytest
from platformdirs import user_cache_dir

from requests_cache.backends import FileCache, FileDict, LRUFileDict
from requests_cache.backends.filesystem import LRUDict
from requests_cache.serializers import (
    SERIALIZERS,
    SerializerPipeline,
    Stage,
    json_serializer,
    safe_pickle_serializer,
    utf8_serializer,
    yaml_serializer,
)
from tests.conftest import CACHE_NAME, HTTPBIN_FORMATS, HTTPBIN_METHODS
from tests.integration.base_cache_test import BaseCacheTest
from tests.integration.base_storage_test import BaseStorageTest

# Handle optional dependencies if they're not installed,
# so any skipped tests will explicitly be shown in pytest output
TEST_SERIALIZERS = SERIALIZERS.copy()
try:
    TEST_SERIALIZERS['safe_pickle'] = safe_pickle_serializer(secret_key='hunter2')
except ImportError:
    TEST_SERIALIZERS['safe_pickle'] = 'safe_pickle_placeholder'


def _valid_serializer(serializer) -> bool:
    return isinstance(serializer, (SerializerPipeline, Stage))


class TestFileDict(BaseStorageTest):
    storage_class = FileDict
    picklable = True

    @classmethod
    def teardown_class(cls):
        rmtree(CACHE_NAME, ignore_errors=True)

    def init_cache(self, index=0, clear=True, **kwargs) -> FileDict:
        cache = self.storage_class(f'{CACHE_NAME}_{index}', use_temp=True, **kwargs)
        if clear:
            cache.clear()
        return cache

    def test_use_cache_dir(self):
        relative_path = self.storage_class(CACHE_NAME).cache_dir
        cache_dir_path = self.storage_class(CACHE_NAME, use_cache_dir=True).cache_dir
        assert not str(relative_path).startswith(user_cache_dir())
        assert str(cache_dir_path).startswith(user_cache_dir())

    def test_use_temp(self):
        relative_path = self.storage_class(CACHE_NAME).cache_dir
        temp_path = self.storage_class(CACHE_NAME, use_temp=True).cache_dir
        assert not str(relative_path).startswith(gettempdir())
        assert str(temp_path).startswith(gettempdir())

    def test_custom_extension(self):
        cache = self.init_cache(extension='dat')
        cache['key'] = 'value'
        assert cache._key2path('key').suffix == '.dat'

    def test_size(self):
        """Check that size updates with bytes added/updated/removed."""
        cache = self.init_cache(plaintext=True)
        assert cache.size() == 0

        # Create a 1KB file
        file_content = '0' * 1024
        cache['key'] = file_content
        assert cache.size() == 1026  # +2 for UTF-8 BOM

        cache.clear()
        assert cache.size() == 0


class TestLRUFileDict(TestFileDict):
    """Test the LRUFileDict with the same tests as the FileDict."""

    storage_class = LRUFileDict

    def init_cache(
        self,
        index=0,
        clear=True,
        max_cache_bytes=10000,
        block_bytes=1,
        plaintext=False,
        **kwargs,
    ) -> LRUFileDict:
        """Initialize a LRUFileDict with common test parameters.

        Args:
            shared_cache_name: If provided, use this exact cache name (for multi-process simulation).
                              If None, create a unique cache name for isolation.
        """
        if plaintext:
            kwargs['serializer'] = None

        cache = self.storage_class(
            f'{CACHE_NAME}_{index}',
            use_temp=True,
            max_cache_bytes=max_cache_bytes,
            block_bytes=block_bytes,
            **kwargs,
        )
        if clear:
            cache.clear()
        return cache

    @pytest.mark.parametrize('block_bytes', [0, -1, 101])
    def test_init__invalid_block_bytes(self, block_bytes):
        """This block size is invalid."""
        with pytest.raises(ValueError):
            self.init_cache(
                max_file_bytes=100,
                max_cache_bytes=100,
                block_bytes=block_bytes,
            )

    def test_init__invalid_max_file_size(self):
        """Cannot have file size greater than maximum cache size."""
        with pytest.raises(ValueError):
            self.init_cache(
                max_file_bytes=1000,
                max_cache_bytes=100,
                block_bytes=100,
            )

    def test_init__max_file_bytes_defaults_to_max_size(self):
        """The argument is initialized properly."""
        lfd = self.init_cache(max_cache_bytes=100, block_bytes=100)
        assert lfd.max_file_bytes == lfd.max_cache_bytes == 100

    def test_init__shared_lock(self):
        """Test passing the lock parameter."""
        lock = RLock()
        cache1 = self.init_cache(lock=lock)
        cache2 = self.init_cache(lock=lock)
        cache3 = self.init_cache()
        assert cache1.lock is cache2.lock
        assert cache1.lock is not cache3.lock

    def test_multiple_cache_instances(self):
        """Multiple cache instances should see the same files."""
        lfd = self.init_cache()
        lfd2 = self.init_cache()

        # Adding items
        lfd['key'] = 'value'
        assert 'key' in lfd
        assert 'key' in lfd2

        # Replacing items
        lfd['key'] = 'new_value'
        assert lfd2['key'] == 'new_value'

        # Removing items
        del lfd['key']
        assert 'key' not in lfd2

    @pytest.mark.parametrize('max_cache_bytes', [1000, 10000])
    def test_do_not_store_files_too_big(self, max_cache_bytes: int):
        """If a file is too big, it should not be cached at all."""
        lfd = self.init_cache(max_cache_bytes=max_cache_bytes)
        file_content = '0' * (max_cache_bytes + 1)
        lfd['key'] = file_content
        assert 'key' not in lfd.keys()

    @pytest.mark.parametrize('files_on_disk', [3, 100])
    def test_evict_oldest_files(self, files_on_disk: int):
        """Check that the files are added up to the size.

        After adding, the least recently used files are removed.
        """
        max_cache_bytes = 1000
        lfd = self.init_cache(max_cache_bytes=max_cache_bytes, plaintext=True)
        file_content = '0' * (max_cache_bytes // files_on_disk)
        for i in range(files_on_disk):
            lfd[f'key_{i}'] = file_content
        assert len(list(lfd.paths())) == files_on_disk, (
            f'Expecting {files_on_disk} files with size '
            f'{len(file_content)}, got {len(list(lfd.paths()))}: '
            f'{sorted(lfd.paths())}'
        )
        assert len(lfd) == files_on_disk
        lfd['new_file'] = file_content
        assert len(list(lfd.paths())) == files_on_disk, 'One file should be dropped.'
        assert 'key_0' not in lfd.keys(), 'File key_0 should be dropped because it is the last one.'

    def test_evict__already_deleted(self):
        """Test behahior when a file is being evicted but has already been (manually) deleted on disk"""
        lfd = self.init_cache(max_cache_bytes=1000, plaintext=True)
        lfd['key_0'] = '0' * 500
        sleep(0.01)
        lfd['key_1'] = '0' * 500

        # Manually delete file, so LRU index is now out of sync
        os.unlink(lfd._key2path('key_0'))
        assert 'key_0' not in lfd.keys()

        # Adding this key should trigger eviction
        lfd['key_2'] = '0' * 500
        assert len(lfd) == 2
        assert len(lfd.lru_index) == 2
        assert 'key_0' not in lfd.lru_index

    def test_sync_index(self):
        """With sync_index=True, the LRU index should be updated on init for any manual file changes."""
        lfd = self.init_cache(max_cache_bytes=1000, plaintext=True)
        lfd['key_0'] = '0' * 100
        sleep(0.01)
        lfd['key_1'] = '0' * 100

        # Manually delete a file outside of cache interface
        os.unlink(lfd._key2path('key_0'))

        # Index should be updated on init
        lfd = self.init_cache(max_cache_bytes=1000, sync_index=True, plaintext=True, clear=False)
        lfd._evict(100)
        assert len(lfd) == 1
        assert len(lfd.lru_index) == 1

    def test_large_file_evicts_all(self):
        """If we add a big file, we should delete everything."""
        lfd = self.init_cache(max_cache_bytes=1000, plaintext=True)
        for i in range(100):
            lfd[f'key_{i}'] = '1' * 10
        lfd['big_file'] = '0' * 1000
        assert lfd.keys() == ['big_file']

    def test_size(self):
        """Check that size updates with bytes added/updated/removed."""
        cache = self.init_cache(plaintext=True)
        assert cache.size() == 0
        assert len(cache.keys()) == 0
        assert len(cache) == 0

        # Adding items
        cache['key'] = 'value'
        assert cache.size() == len('value')
        cache['key2'] = 'value2'
        assert cache.size() == len('value') + len('value2')

        # Replacing items
        cache['key'] = 'new_value'
        assert cache.size() == len('new_value') + len('value2')

        # Removing items
        del cache['key2']
        assert cache.size() == len('new_value')

    @pytest.mark.parametrize(
        ('block_bytes', 'file_size', 'expected_size'),
        [
            (1, 10, 10),
            (10, 9, 10),
            (10, 10, 10),
            (10, 11, 20),
            (10, 12, 20),
            (1024, 3, 1024),
            (100, 1111, 1200),
        ],
    )
    def test_get_size_on_disk(self, block_bytes, file_size, expected_size):
        """Compute the block size."""
        cache = self.init_cache(block_bytes=block_bytes)
        assert cache._get_size_on_disk(file_size) == expected_size
        assert cache._get_size_on_disk(-file_size) == -expected_size

    @pytest.mark.parametrize('block_bytes', [1, 10, 128])
    def test_block_alignment(self, block_bytes: int):
        """File size should be aligned with the block on the file system, and be taken into account
        when adding, replacing, and deleting items.
        """
        block_lfd = self.init_cache(block_bytes=block_bytes, plaintext=True)

        # Adding items
        block_lfd['file'] = '0' * 100
        assert block_lfd.size() % block_lfd.block_bytes == 0
        assert block_lfd.size() == block_lfd._get_size_on_disk(100)

        # Replacing items
        block_lfd['file'] = '0' * 123
        assert block_lfd.size() % block_lfd.block_bytes == 0
        assert block_lfd.size() == block_lfd._get_size_on_disk(123)

        # Deleting items
        del block_lfd['file']
        block_lfd['key1'] = '2' * 100
        size_1 = block_lfd.size()
        block_lfd['key2'] = '2' * 123
        size_1_2 = block_lfd.size()
        assert size_1_2 > size_1
        assert size_1_2 % block_lfd.block_bytes == 0
        del block_lfd['key1']
        size_2 = size_1_2 - size_1
        assert block_lfd.size() == size_2
        assert size_2 % block_lfd.block_bytes == 0
        del block_lfd['key2']
        assert block_lfd.size() == 0

    @pytest.mark.parametrize('max_cache_bytes', [5, 6, 7, 8, 9])
    def test_clear_with_unaligned_blocks(self, max_cache_bytes):
        lfd = self.init_cache(
            max_file_bytes=5,
            max_cache_bytes=max_cache_bytes,
            block_bytes=5,
        )
        lfd.clear()
        lfd['x'] = '123'
        assert lfd.size() == 5
        lfd['y'] = ''
        assert lfd.size() == 5
        assert 'x' not in lfd, 'x must have been deleted'


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

    @pytest.mark.parametrize(
        ('sort_key', 'reversed_order', 'limit', 'expected'),
        [
            # Sort by access_time (default)
            ('access_time', False, None, ['key1', 'key2', 'key3']),
            ('access_time', True, None, ['key3', 'key2', 'key1']),
            ('access_time', False, 2, ['key1', 'key2']),
            ('access_time', True, 2, ['key3', 'key2']),
            # Sort by size
            ('size', False, None, ['key1', 'key2', 'key3']),
            ('size', True, None, ['key3', 'key2', 'key1']),
            ('size', False, 2, ['key1', 'key2']),
            # Sort by key (alphabetical)
            ('key', False, None, ['key1', 'key2', 'key3']),
            ('key', True, None, ['key3', 'key2', 'key1']),
        ],
    )
    def test_sorted(self, sort_key, reversed_order, limit, expected):
        cache = self.init_cache()

        # Add items with different sizes and access times
        cache['key1'] = 100
        sleep(0.001)
        cache['key2'] = 200
        sleep(0.001)
        cache['key3'] = 300

        result = list(cache.sorted(key=sort_key, reversed=reversed_order, limit=limit))
        assert result == expected

    def test_sorted__invalid_key(self):
        cache = self.init_cache()
        cache['key1'] = 100

        with pytest.raises(ValueError, match='Invalid sort key: invalid'):
            list(cache.sorted(key='invalid'))

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


class TestFileCache(BaseCacheTest):
    backend_class = FileCache
    init_kwargs = {'use_temp': True}

    @pytest.mark.parametrize('serializer', TEST_SERIALIZERS.values())
    @pytest.mark.parametrize('method', HTTPBIN_METHODS)
    @pytest.mark.parametrize('field', ['params', 'data', 'json'])
    def test_all_methods(self, field, method, serializer):
        """Test all relevant combinations of methods X data fields X serializers"""
        if not _valid_serializer(serializer):
            pytest.skip(f'Dependencies not installed for {serializer}')
        super().test_all_methods(field, method, serializer)

    @pytest.mark.parametrize('serializer', TEST_SERIALIZERS.values())
    @pytest.mark.parametrize('response_format', HTTPBIN_FORMATS)
    def test_all_response_formats(self, response_format, serializer):
        """Test all relevant combinations of response formats X serializers"""
        if not _valid_serializer(serializer):
            pytest.skip(f'Dependencies not installed for {serializer}')
        serializer.set_decode_content(False)
        super().test_all_response_formats(response_format, serializer)

    @pytest.mark.parametrize('serializer', [json_serializer, yaml_serializer])
    @pytest.mark.parametrize('response_format', HTTPBIN_FORMATS)
    def test_all_response_formats__no_decode_content(self, response_format, serializer):
        """Test with decode_content=True for text-based serialization formats"""
        if not _valid_serializer(serializer):
            pytest.skip(f'Dependencies not installed for {serializer}')
        serializer.set_decode_content(True)
        self.test_all_response_formats(response_format, serializer)

    @pytest.mark.parametrize('serializer_name', SERIALIZERS.keys())
    def test_paths(self, serializer_name):
        if not isinstance(SERIALIZERS[serializer_name], SerializerPipeline):
            pytest.skip(f'Dependencies not installed for {serializer_name}')

        session = self.init_session(serializer=serializer_name)
        num_files = 20
        for i in range(num_files):
            session.cache.responses[f'key_{i}'] = {f'value_{i}': i}

        expected_extension = serializer_name.replace('pickle', 'pkl')
        if 'json' in serializer_name:
            expected_extension = 'json'
        assert len(list(session.cache.paths())) == num_files
        for path in session.cache.paths():
            assert path.is_file()
            assert path.suffix == f'.{expected_extension}'

        # Redirects db should be in the same directory as response files
        assert session.cache.redirects.db_path.parent == session.cache.responses.cache_dir

    @pytest.mark.parametrize('max_cache_bytes', [1000, 10000])
    @pytest.mark.parametrize('files_on_disk', [3, 100])
    def test_drop_oldest_files(self, max_cache_bytes, files_on_disk):
        """Check that the files are added up to the size.

        After adding, the first ones are dropped.
        """
        file_content = '0' * (max_cache_bytes // files_on_disk - 2)  # remove UTF8 BOM
        session = self.init_session(max_cache_bytes=max_cache_bytes, block_bytes=1)
        for i in range(files_on_disk):
            session.cache.responses[f'key_{i}'] = file_content
        assert len(list(session.cache.paths())) == files_on_disk, (
            f'Expecting {files_on_disk} files with size {len(file_content)}, got {len(list(session.cache.paths()))}'
        )
        assert len(list(session.cache.paths())) == files_on_disk
        session.cache.responses['new_file'] = file_content
        assert len(list(session.cache.paths())) == files_on_disk, 'One file should be dropped.'
        assert 'key_0' not in session.cache.responses.keys(), (
            'File key_0 should be dropped because it is the last one.'
        )

    @pytest.mark.parametrize('max_size_on_disk', [1000, 10000])
    def test_do_not_store_files_too_big(self, max_size_on_disk):
        """If a file is too big, it should not be cached at all."""
        file_content = '0' * (max_size_on_disk + 1)
        session = self.init_session(max_cache_bytes=max_size_on_disk, block_bytes=1)
        session.cache.responses['key'] = file_content
        assert 'key' not in session.cache.responses.keys()

    def test_size(self):
        """Check that the total bytes are summed up if files are added."""
        session = self.init_session(max_cache_bytes=100, block_bytes=1, serializer=utf8_serializer)
        start_bytes = session.cache.responses.size()
        session.cache.responses['key_1'] = 'value_1'
        assert session.cache.responses.size() == start_bytes + len('value_1')
