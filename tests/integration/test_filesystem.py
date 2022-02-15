from shutil import rmtree
from tempfile import gettempdir

import pytest
from appdirs import user_cache_dir

from requests_cache.backends import FileCache, FileDict
from requests_cache.serializers import SERIALIZERS, SerializerPipeline
from tests.integration.base_cache_test import BaseCacheTest
from tests.integration.base_storage_test import CACHE_NAME, BaseStorageTest


class TestFileDict(BaseStorageTest):
    storage_class = FileDict
    picklable = True

    @classmethod
    def teardown_class(cls):
        rmtree(CACHE_NAME, ignore_errors=True)

    def init_cache(self, index=0, clear=True, **kwargs):
        cache = FileDict(f'{CACHE_NAME}_{index}', serializer='pickle', use_temp=True, **kwargs)
        if clear:
            cache.clear()
        return cache

    def test_use_cache_dir(self):
        relative_path = FileDict(CACHE_NAME).cache_dir
        cache_dir_path = FileDict(CACHE_NAME, use_cache_dir=True).cache_dir
        assert not str(relative_path).startswith(user_cache_dir())
        assert str(cache_dir_path).startswith(user_cache_dir())

    def test_use_temp(self):
        relative_path = FileDict(CACHE_NAME).cache_dir
        temp_path = FileDict(CACHE_NAME, use_temp=True).cache_dir
        assert not str(relative_path).startswith(gettempdir())
        assert str(temp_path).startswith(gettempdir())

    def test_load_previous_binary_file(self):
        """If we init a new cache and load a file previously saved in binary mode, the cache should
        handle this and open future files in binary mode for the rest of the session.
        """
        cache = self.init_cache()
        cache['foo'] = 'bar'

        cache = self.init_cache(clear=False)
        assert cache['foo'] == 'bar'
        assert cache.is_binary is True


class TestFileCache(BaseCacheTest):
    backend_class = FileCache
    init_kwargs = {'use_temp': True}

    @pytest.mark.parametrize('serializer_name', SERIALIZERS.keys())
    def test_paths(self, serializer_name):
        if not isinstance(SERIALIZERS[serializer_name], SerializerPipeline):
            pytest.skip(f'Dependencies not installed for {serializer_name}')

        session = self.init_session(serializer=serializer_name)
        num_files = 20
        for i in range(num_files):
            session.cache.responses[f'key_{i}'] = {f'value_{i}': i}

        expected_extension = serializer_name.replace('pickle', 'pkl')
        assert len(list(session.cache.paths())) == num_files
        for path in session.cache.paths():
            assert path.is_file()
            assert path.suffix == f'.{expected_extension}'

        # Redirects db should be in the same directory as response files
        assert session.cache.redirects.db_path.parent == session.cache.responses.cache_dir
