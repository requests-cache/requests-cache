from sys import version_info

import pytest

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

    # TODO: Remove when fixed
    def test_response_no_duplicate_read(self):
        if version_info >= (3, 12):
            pytest.xfail('Known (very minor) bug with python 3.12')
        super().test_response_no_duplicate_read()
