from shutil import rmtree
from tempfile import gettempdir

import pytest
from platformdirs import user_cache_dir

from requests_cache.backends import FileCache, FileDict
from requests_cache.serializers import (
    SERIALIZERS,
    SerializerPipeline,
    Stage,
    json_serializer,
    safe_pickle_serializer,
    yaml_serializer,
)
from tests.conftest import HTTPBIN_FORMATS, HTTPBIN_METHODS
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


class TestFileDict(BaseStorageTest):
    storage_class = FileDict
    picklable = True

    @classmethod
    def teardown_class(cls):
        rmtree(CACHE_NAME, ignore_errors=True)

    def init_cache(self, index=0, clear=True, **kwargs):
        cache = FileDict(f'{CACHE_NAME}_{index}', use_temp=True, **kwargs)
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

    def test_custom_extension(self):
        cache = self.init_cache(extension='dat')
        cache['key'] = 'value'
        assert cache._path('key').suffix == '.dat'


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
        assert len(list(session.cache.paths())) == num_files
        for path in session.cache.paths():
            assert path.is_file()
            assert path.suffix == f'.{expected_extension}'

        # Redirects db should be in the same directory as response files
        assert session.cache.redirects.db_path.parent == session.cache.responses.cache_dir
