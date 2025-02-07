from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from shutil import rmtree
from sys import version_info
from tempfile import gettempdir
from threading import RLock
from typing import Generator

import pytest
from platformdirs import user_cache_dir

from requests_cache.backends import FileCache, FileDict
from requests_cache.backends.filesystem import LimitedFileDict
from requests_cache.serializers import (
    SERIALIZERS,
    SerializerPipeline,
    Stage,
    json_serializer,
    safe_pickle_serializer,
    yaml_serializer,
    utf8_serializer,
)
from tests.conftest import HTTPBIN_FORMATS, HTTPBIN_METHODS, N_ITERATIONS
from tests.integration.base_cache_test import BaseCacheTest
from tests.integration.base_storage_test import CACHE_NAME, BaseStorageTest

# Handle optional dependencies if they're not installed,
# so any skipped tests will explicitly be shown in pytest output
TEST_SERIALIZERS = SERIALIZERS.copy()
try:
    TEST_SERIALIZERS['safe_pickle'] = safe_pickle_serializer(secret_key='hunter2')
except ImportError:
    TEST_SERIALIZERS['safe_pickle'] = 'safe_pickle_placeholder'


def _valid_serializer(serializer) -> bool:
    return isinstance(serializer, (SerializerPipeline, Stage))


@pytest.fixture(params=[1000, 10000])
def maximum_cache_bytes(request) -> int:
    """The maximum total bytes for the FileDict/FileCache."""
    return request.param


@pytest.fixture()
def lfd(
    request: pytest.FixtureRequest, maximum_cache_bytes: int
) -> Generator[LimitedFileDict, None, None]:
    """An instance of a LimitedFileDict.

    This is useful to simulate multiple processes.
    """
    yield from new_lfd(request, maximum_cache_bytes)


def new_lfd(
    request: pytest.FixtureRequest, maximum_cache_bytes: int, block_bytes: int = 1
) -> Generator[LimitedFileDict, None, None]:
    cache = LimitedFileDict(
        f'{CACHE_NAME}_file_dict_{request.function.__name__}',
        serializer=utf8_serializer,
        maximum_cache_bytes=maximum_cache_bytes,
        use_temp=True,
        block_bytes=block_bytes,
    )
    cache.clear()
    yield cache
    try:
        print(cache.debug_state(30))
    finally:
        cache.clear()
        rmtree(cache.cache_dir)


@pytest.fixture()
def lfd2(
    request: pytest.FixtureRequest, maximum_cache_bytes: int
) -> Generator[LimitedFileDict, None, None]:
    """A second instance working on the same directory.

    This is useful to simulate multiple processes.
    """
    yield from new_lfd(request, maximum_cache_bytes)


@pytest.fixture()
def broken_lfd(lfd: LimitedFileDict) -> LimitedFileDict:
    """Return the lft with a broken state."""
    lfd['first'] = '1'
    lfd['second'] = '2'
    lfd['third'] = '3'
    rmtree(lfd.cache_dir / 'second.utf8')
    (lfd.cache_dir / 'first.utf8' / '0').unlink()
    return lfd


@pytest.fixture(params=['first', 'second'])
def broken_key(request: pytest.FixtureRequest) -> str:
    """Return a key that has a broken state in broken_lfd."""
    return request.param


@pytest.fixture(params=[1, 10, 128])
def block_lfd(request: pytest.FixtureRequest) -> Generator[LimitedFileDict, None, None]:
    """Return a LimitedFileDict with a custom block size."""
    yield from new_lfd(request, 1000, block_bytes=request.param)


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


class TestLimitedFileDict(TestFileDict):
    """Test the LimitedFileDict with the same tests as the FileDict."""

    storage_class = LimitedFileDict

    def test_create_with_lock(self):
        """Test passing the lock parameter."""
        lock = RLock()
        cache1 = self.init_cache(lock=lock)
        cache2 = self.init_cache(lock=lock)
        cache3 = self.init_cache()
        assert cache1.lock is cache2.lock
        assert cache1.lock is not cache3.lock


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

    # TODO: Remove after fixing issue with SQLite multiprocessing on python 3.12
    @pytest.mark.parametrize('executor_class', [ThreadPoolExecutor, ProcessPoolExecutor])
    @pytest.mark.parametrize('iteration', range(N_ITERATIONS))
    def test_concurrency(self, iteration, executor_class):
        if version_info >= (3, 12):
            pytest.xfail('Concurrent usage of SQLite backend is not yet supported on python 3.12')
        super().test_concurrency(iteration, executor_class)

    @pytest.mark.parametrize('maximum_size_on_disk', [1000, 10000])
    @pytest.mark.parametrize('files_on_disk', [3, 100])
    def test_drop_oldest_files(self, maximum_size_on_disk, files_on_disk):
        """Check that the files are added up to the size.

        After adding, the first ones are dropped.
        """
        file_content = '0' * (maximum_size_on_disk // files_on_disk - 2)  # remove UTF8 BOM
        session = self.init_session(maximum_cache_bytes=maximum_size_on_disk, block_bytes=1)
        for i in range(files_on_disk):
            session.cache.responses[f'key_{i}'] = file_content
        assert (
            len(list(session.cache.paths())) == files_on_disk
        ), f'Expecting {files_on_disk} files with size {len(file_content)}, got {len(list(session.cache.paths()))}'
        assert len(list(session.cache.paths())) == files_on_disk
        session.cache.responses['new_file'] = file_content
        assert len(list(session.cache.paths())) == files_on_disk, 'One file should be dropped.'
        assert (
            'key_0' not in session.cache.responses.keys()
        ), 'File key_0 should be dropped because it is the last one.'

    @pytest.mark.parametrize('maximum_size_on_disk', [1000, 10000])
    def test_do_not_store_files_too_big(self, maximum_size_on_disk):
        """If a file is too big, it should not be cached at all."""
        file_content = '0' * (maximum_size_on_disk + 1)
        session = self.init_session(maximum_cache_bytes=maximum_size_on_disk, block_bytes=1)
        session.cache.responses['key'] = file_content
        assert 'key' not in session.cache.responses.keys()

    def test_total_bytes_is_calculated_correctly(self):
        """Check that the total bytes are summed up if files are added."""
        session = self.init_session(
            maximum_cache_bytes=100, serializer=utf8_serializer, block_bytes=1
        )
        start_bytes = session.cache.responses.total_bytes
        session.cache.responses['key_1'] = 'value_1'
        assert session.cache.responses.total_bytes == start_bytes + len('value_1')


def test_total_size_is_0_at_the_start(lfd: LimitedFileDict):
    """Check the we start with 0 bytes."""
    assert lfd.total_bytes == 0
    assert len(lfd.keys()) == 0
    assert len(lfd) == 0


def test_file_dict_increases_size_when_adding_items(lfd: LimitedFileDict):
    """Check that we increase the size by the amount of bytes added."""
    lfd['key'] = 'value'
    assert lfd.total_bytes == len('value')
    lfd['key2'] = 'value2'
    assert lfd.total_bytes == len('value') + len('value2')


ITEMS = ['', '1234567', '123456789']


@pytest.mark.parametrize('remove', ITEMS)
@pytest.mark.parametrize('multiplier', [1, 5])
def test_removing_an_item_reduces_the_total_size(
    lfd: LimitedFileDict, multiplier: int, remove: str
):
    """When removing items the total size is reduced accordingly."""
    for item in ITEMS:
        lfd[item] = item * multiplier
    total_size = lfd.total_bytes
    del lfd[remove]
    assert lfd.total_bytes == total_size - len(remove) * multiplier


@pytest.mark.parametrize('new_value', ['123456789', '123'])
def test_replacing_an_items_changes_the_total_size(lfd: LimitedFileDict, new_value: str):
    """When replacing items the total size is reduced or increased accordingly."""
    lfd['v'] = '12345'
    lfd['v'] = new_value
    assert lfd.total_bytes == len(new_value)


def test_no_error_if_cache_is_empty(lfd: LimitedFileDict):
    """We should be safe to drop files if we have no files in the cache."""
    lfd.drop_oldest_key()


def test_do_not_store_files_too_big(maximum_cache_bytes: int, lfd: LimitedFileDict):
    """If a file is too big, it should not be cached at all."""
    file_content = '0' * (maximum_cache_bytes + 1)
    lfd['key'] = file_content
    assert 'key' not in lfd.keys()


@pytest.mark.parametrize('files_on_disk', [3, 100])
def test_drop_oldest_files(maximum_cache_bytes: int, files_on_disk: int, lfd: LimitedFileDict):
    """Check that the files are added up to the size.

    After adding, the first ones are dropped.
    """
    file_content = '0' * (maximum_cache_bytes // files_on_disk)
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


@pytest.mark.parametrize('utf8_value', ['\u1224', '\u1224\u0034🠚'])
def test_size_of_cache_is_in_bytes(lfd: LimitedFileDict, utf8_value: str):
    """We check that UTF8 characters take up 2 bytes."""
    lfd['key'] = utf8_value
    assert lfd.total_bytes == len(utf8_value.encode('utf-8'))


def test_clearing_empties_cache(lfd: LimitedFileDict):
    """Clear should reset the state."""
    lfd['key'] = 'value'
    lfd.clear()
    assert lfd.total_bytes == 0


def test_cannot_have_file_size_greater_than_maximum_cache_size():
    """The arguments must make sense."""
    with pytest.raises(ValueError):
        LimitedFileDict(
            'cache',
            maximum_file_bytes=1000,
            maximum_cache_bytes=100,
            use_temp=True,
            block_bytes=100,
        )


def test_maximum_file_bytes_is_same_as_max_size_if_not_given():
    """The argument is initialized properly."""
    lfd = LimitedFileDict('test_cache', maximum_cache_bytes=100, use_temp=True, block_bytes=100)
    assert lfd.maximum_file_bytes == lfd.maximum_cache_bytes == 100


def test_file_is_created_in_other_process(lfd: LimitedFileDict, lfd2: LimitedFileDict):
    """The keys get synced."""
    lfd['key'] = 'value'
    assert 'key' in lfd
    assert 'key' in lfd2


def test_file_is_deleted_in_other_process(lfd: LimitedFileDict, lfd2: LimitedFileDict):
    """Check the deletion is synced."""
    lfd['key.1'] = 'value'
    del lfd2['key.1']
    assert 'key.1' not in lfd
    assert 'key.1' not in lfd2


@pytest.mark.parametrize('delete_before', [True, False])
def test_update_value_in_other_process(
    lfd: LimitedFileDict, lfd2: LimitedFileDict, delete_before: bool
):
    """Check that the value is transported."""
    lfd['key.2'] = 'value'
    if delete_before:
        del lfd2['key.2']
    lfd2['key.2'] = 'value2'
    assert lfd['key.2'] == 'value2'
    assert lfd2['key.2'] == 'value2'


@pytest.mark.parametrize('new_size', [10, 5, 1])
def test_replacing_a_value_does_not_delete_the_value_before(
    lfd: LimitedFileDict, maximum_cache_bytes: int, new_size: int
):
    """If we replace a value, the other keys should be left untouched if replacement is possible."""
    # fill it up until it is full
    lfd['big.file'] = big_file = '0' * (maximum_cache_bytes - 11)
    lfd['small.file'] = '1' * 10  # we fill it until max - 1
    lfd['small.file'] = small_file = '2' * new_size
    assert lfd['small.file'] == small_file
    assert lfd['big.file'] == big_file


def test_delete_all_when_adding_a_big_file(lfd: LimitedFileDict, maximum_cache_bytes: int):
    """If we add a big file, we should delete everything."""
    for i in range(maximum_cache_bytes // 10):
        lfd[f'key_{i}'] = '1' * 10
    lfd['big_file'] = '0' * maximum_cache_bytes
    assert lfd.keys() == ['big_file']


def test_invalid_state_file_removed_set_value(broken_lfd: LimitedFileDict, broken_key: str):
    """Invalid state because of concurrency."""
    broken_lfd[broken_key] = 'xxx'
    assert broken_key in broken_lfd
    assert broken_lfd[broken_key] == 'xxx'


def test_invalid_state_file_removed_del_value(broken_lfd: LimitedFileDict, broken_key: str):
    """Invalid state because of concurrency."""
    assert broken_key not in broken_lfd
    assert broken_key not in broken_lfd.keys()
    with pytest.raises(KeyError):
        del broken_lfd[broken_key]


def test_invalid_state_file_removed_get_value(broken_lfd: LimitedFileDict, broken_key: str):
    """Invalid state because of concurrency."""
    with pytest.raises(KeyError):
        broken_lfd[broken_key]


def test_invalid_state_file_removed_drop_value(broken_lfd: LimitedFileDict):
    """Invalid state because of concurrency."""
    broken_lfd.drop_oldest_key()
    broken_lfd.drop_oldest_key()
    broken_lfd.drop_oldest_key()
    assert len(broken_lfd) == 0


def test_versions_are_increasing_for_content(lfd: LimitedFileDict, lfd2: LimitedFileDict):
    """The versions should be increased to make sure we do update the size."""
    lfd['key'] = 'value'
    del lfd2['key']
    assert lfd.total_bytes == 0
    lfd['key'] = '1234567'
    assert lfd2.total_bytes == len('1234567'.encode('utf-8'))


def test_size_is_updated_even_if_key_is_replaced(lfd: LimitedFileDict, lfd2: LimitedFileDict):
    """The size needs to be updated even if we replace the key in another process."""
    lfd['key'] = '123'
    del lfd2['key']
    lfd2['key'] = '12345'
    assert lfd.total_bytes == lfd2.total_bytes == len('12345'.encode('utf-8'))


def test_getting_the_oldest_key_of_empty_cache(lfd: LimitedFileDict):
    """The id should be None."""
    assert lfd.get_oldest_key()[0] is None
    assert lfd.get_oldest_key()[0] is None


def test_oldest_key_set(lfd: LimitedFileDict, lfd2: LimitedFileDict):
    """The oldest key should work with deleted values."""
    lfd['key'] = '123'
    assert lfd.get_oldest_key()[0] == 'key'
    assert lfd2.get_oldest_key()[0] == 'key'


def test_oldest_key_deleted(lfd: LimitedFileDict, lfd2: LimitedFileDict):
    """The oldest key should work with deleted values."""
    lfd['key'] = '123'
    del lfd2['key']
    assert lfd.get_oldest_key()[0] is None
    assert lfd2.get_oldest_key()[0] is None


def test_oldest_key_deleted_new_value(lfd: LimitedFileDict, lfd2: LimitedFileDict):
    """The oldest key should work with deleted values."""
    lfd['key'] = '123'
    lfd['key2'] = '123'
    del lfd2['key']
    assert lfd.get_oldest_key()[0] == 'key2'
    assert lfd2.get_oldest_key()[0] == 'key2'


def test_oldest_key_stays(lfd: LimitedFileDict, lfd2: LimitedFileDict):
    """The oldest key should stay when a newer key is added."""
    lfd['key'] = '123'
    lfd['key2'] = '123'
    assert lfd.get_oldest_key()[0] == 'key'
    assert lfd2.get_oldest_key()[0] == 'key'


def test_oldest_key_changes(lfd: LimitedFileDict, lfd2: LimitedFileDict):
    """The oldest key change if it is renewed."""
    lfd['key'] = '123'
    lfd['key2'] = '123'
    lfd['key'] = '123'
    assert lfd.get_oldest_key()[0] == 'key2'
    assert lfd2.get_oldest_key()[0] == 'key2'


def test_file_id_increases(lfd: LimitedFileDict):
    """The file id should increase."""
    assert lfd.get_new_file_id() == 0
    assert lfd.get_new_file_id() == 1


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
def test_compute_block_bytes(block_bytes, file_size, expected_size):
    """Compute the block size."""
    assert LimitedFileDict.compute_file_size(block_bytes, file_size) == expected_size
    assert LimitedFileDict.compute_file_size(block_bytes, -file_size) == -expected_size


@pytest.mark.parametrize('block_bytes', [0, -1])
def test_invalid_block_bytes(block_bytes):
    """This block size is invalid."""
    with pytest.raises(ValueError):
        LimitedFileDict(
            'cache',
            maximum_file_bytes=10,
            maximum_cache_bytes=10,
            use_temp=True,
            block_bytes=block_bytes,
        )


def test_upper_limit_of_block_bytes():
    """This block size is invalid."""
    with pytest.raises(ValueError):
        LimitedFileDict(
            'cache',
            maximum_file_bytes=100,
            maximum_cache_bytes=1000,
            use_temp=True,
            block_bytes=101,
        )
    with pytest.raises(ValueError):
        LimitedFileDict(
            'cache', maximum_file_bytes=100, maximum_cache_bytes=100, use_temp=True, block_bytes=101
        )
    lfd = LimitedFileDict(
        'cache', maximum_file_bytes=100, maximum_cache_bytes=100, use_temp=True, block_bytes=100
    )
    assert lfd.block_bytes == 100


def test_file_size_is_aligned_with_block_size(block_lfd: LimitedFileDict):
    """The size of the files is computed as aligned with the block on the file system."""
    block_lfd['file'] = '0' * 100
    assert block_lfd.total_bytes % block_lfd.block_bytes == 0
    assert block_lfd.total_bytes == block_lfd.compute_file_size(block_lfd.block_bytes, 100)


def test_make_sure_size_is_used_for_replace(block_lfd: LimitedFileDict):
    """All computations should adhere to block size."""
    block_lfd['key'] = '1'
    assert block_lfd.total_bytes == block_lfd.block_bytes
    block_lfd['key'] = '2' * 100
    assert block_lfd.total_bytes % block_lfd.block_bytes == 0
    assert block_lfd.total_bytes == block_lfd.compute_file_size(block_lfd.block_bytes, 100)


def test_make_sure_size_is_used_for_delete(block_lfd: LimitedFileDict):
    """All computations should adhere to block size."""
    block_lfd['key1'] = '2' * 100
    size_1 = block_lfd.total_bytes
    block_lfd['key2'] = '2' * 123
    size_1_2 = block_lfd.total_bytes
    assert size_1_2 > size_1
    assert size_1_2 % block_lfd.block_bytes == 0
    del block_lfd['key1']
    size_2 = size_1_2 - size_1
    assert block_lfd.total_bytes == size_2
    assert size_2 % block_lfd.block_bytes == 0
    del block_lfd['key2']
    assert block_lfd.total_bytes == 0


@pytest.mark.parametrize('maximum_cache_bytes', [5, 6, 7, 8, 9])
def test_free_up_space_with_unaligned_blocks(maximum_cache_bytes):
    lfd = LimitedFileDict(
        'cache',
        maximum_file_bytes=5,
        maximum_cache_bytes=maximum_cache_bytes,
        use_temp=True,
        block_bytes=5,
    )
    lfd.clear()
    lfd['x'] = '123'
    assert lfd.total_bytes == 5
    lfd['y'] = ''
    assert lfd.total_bytes == 5
    assert 'x' not in lfd, 'x must have been deleted'
