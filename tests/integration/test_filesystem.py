import pickle
from os.path import dirname, isfile
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

    def init_cache(self, index=0, **kwargs):
        cache = self.storage_class(f'{CACHE_NAME}_{index}', serializer=pickle, use_temp=True, **kwargs)
        cache.clear()
        return cache

    def test_use_cache_dir(self):
        relative_path = self.storage_class(CACHE_NAME).cache_dir
        cache_dir_path = self.storage_class(CACHE_NAME, use_cache_dir=True).cache_dir
        assert not relative_path.startswith(user_cache_dir())
        assert cache_dir_path.startswith(user_cache_dir())

    def test_use_temp(self):
        relative_path = self.storage_class(CACHE_NAME).cache_dir
        temp_path = self.storage_class(CACHE_NAME, use_temp=True).cache_dir
        assert not relative_path.startswith(gettempdir())
        assert temp_path.startswith(gettempdir())


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
            session.cache.responses[f'key_{i}'] = f'value_{i}'

        expected_extension = serializer_name.replace('pickle', 'pkl')
        assert len(list(session.cache.paths())) == num_files
        for path in session.cache.paths():
            assert isfile(path)
            assert path.endswith(f'.{expected_extension}')

        # Redirects db should be in the same directory as response files
        assert dirname(session.cache.redirects.db_path) == session.cache.responses.cache_dir
