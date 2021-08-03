import pickle
import pytest
from os.path import isfile
from shutil import rmtree
from tempfile import gettempdir

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

    def test_use_temp(self):
        relative_path = self.storage_class(CACHE_NAME).cache_dir
        temp_path = self.storage_class(CACHE_NAME, use_temp=True).cache_dir
        assert not relative_path.startswith(gettempdir())
        assert temp_path.startswith(gettempdir())

    @pytest.mark.parametrize('serializer_name', SERIALIZERS.keys())
    def test_paths(self, serializer_name):
        if not isinstance(SERIALIZERS[serializer_name], SerializerPipeline):
            pytest.skip(f'Dependencies not installed for {serializer_name}')

        cache = self.storage_class(CACHE_NAME, serializer=serializer_name)
        cache.clear()
        for i in range(self.num_instances):
            cache[f'key_{i}'] = f'value_{i}'

        expected_extension = serializer_name.replace('pickle', 'pkl')
        assert len(list(cache.paths())) == self.num_instances
        for path in cache.paths():
            assert isfile(path)
            assert path.endswith(f'.{expected_extension}')


class TestFileCache(BaseCacheTest):
    backend_class = FileCache
    init_kwargs = {'use_temp': True}
