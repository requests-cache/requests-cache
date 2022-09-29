from sqlalchemy import create_engine

from requests_cache import ALL_METHODS, CachedSession
from requests_cache.backends import DbCache, DbDict
from tests.integration.base_cache_test import BaseCacheTest
from tests.integration.base_storage_test import BaseStorageTest

# class TestDbDict(BaseStorageTest):
#     storage_class = DbDict


class TestDbCache(BaseCacheTest):
    backend_class = DbCache

    def init_session(self, clear=True, **kwargs) -> CachedSession:
        kwargs.setdefault('allowable_methods', ALL_METHODS)
        engine = create_engine('postgresql://postgres:hunter2@localhost:5432/postgres')
        backend = DbCache(engine, **kwargs)
        if clear:
            backend.clear()

        return CachedSession(backend=backend, **kwargs)
