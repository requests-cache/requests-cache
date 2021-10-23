from requests_cache.backends import BaseCache, DictStorage
from tests.integration.base_cache_test import BaseCacheTest
from tests.integration.base_storage_test import BaseStorageTest


class TestMemoryDict(BaseStorageTest):
    storage_class = DictStorage

    def init_cache(self, clear=True, **kwargs):
        cache = self.storage_class(**kwargs)
        if clear:
            cache.clear()
        return cache

    def test_same_settings(self):
        """This test from base class doesn't apply here"""


class TestMemoryCache(BaseCacheTest):
    backend_class = BaseCache
