from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from logging import getLogger
from time import sleep
from unittest.mock import patch

import pytest
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from requests_cache.backends import GridFSCache, GridFSDict, MongoCache, MongoDict
from requests_cache.policy import NEVER_EXPIRE
from tests.conftest import N_ITERATIONS, fail_if_no_connection, httpbin
from tests.integration.base_cache_test import BaseCacheTest
from tests.integration.base_storage_test import BaseStorageTest

try:
    from pymongo.errors import ServerSelectionTimeoutError
except ImportError:
    pass

logger = getLogger(__name__)


@pytest.fixture(scope='module', autouse=True)
@fail_if_no_connection(connect_timeout=2)
def ensure_connection():
    """Fail all tests in this module if MongoDB is not running"""
    from pymongo import MongoClient

    client = MongoClient(serverSelectionTimeoutMS=2000)
    client.server_info()


class TestMongoDict(BaseStorageTest):
    storage_class = MongoDict

    def test_connection_kwargs(self):
        """A spot check to make sure optional connection kwargs gets passed to connection"""
        # MongoClient prevents direct access to private members like __init_kwargs;
        # need to test indirectly using its repr
        cache = MongoDict(
            'test',
            host='mongodb://0.0.0.0',
            port=2222,
            tz_aware=True,
            connect=False,
            invalid_kwarg='???',
        )
        assert "host=['0.0.0.0:2222']" in repr(cache.connection)
        assert "tz_aware=True" in repr(cache.connection)


class TestMongoCache(BaseCacheTest):
    backend_class = MongoCache

    def test_ttl(self):
        session = self.init_session()
        session.cache.set_ttl(1)

        session.get(httpbin('get'))
        response = session.get(httpbin('get'))
        assert response.from_cache is True

        # Wait for removal background process to run
        # Unfortunately there doesn't seem to be a way to manually trigger it
        for i in range(70):
            if response.cache_key not in session.cache.responses:
                logger.debug(f'Removed {response.cache_key} after {i} seconds')
                break
            sleep(1)

        assert response.cache_key not in session.cache.responses

    def test_ttl__overwrite(self):
        session = self.init_session()
        session.cache.set_ttl(60)

        # Should have no effect
        session.cache.set_ttl(360)
        assert session.cache.get_ttl() == 60

        # Should create new index
        session.cache.set_ttl(360, overwrite=True)
        assert session.cache.get_ttl() == 360

        # Should drop index
        session.cache.set_ttl(None, overwrite=True)
        assert session.cache.get_ttl() is None

        # Should attempt to drop non-existent index and ignore error
        session.cache.set_ttl(NEVER_EXPIRE, overwrite=True)
        assert session.cache.get_ttl() is None

    @retry(
        retry=retry_if_exception_type(ServerSelectionTimeoutError),
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_fixed(5),
    )
    @pytest.mark.parametrize('executor_class', [ThreadPoolExecutor, ProcessPoolExecutor])
    @pytest.mark.parametrize('iteration', range(N_ITERATIONS))
    def test_concurrency(self, iteration, executor_class):
        """On GitHub runners, sometimes the MongoDB container is not ready yet by the time this,
        runs, so some retries are added here.
        """
        super().test_concurrency(iteration, executor_class)


class TestGridFSDict(BaseStorageTest):
    storage_class = GridFSDict
    picklable = True
    num_instances = 1  # Only test a single collecton instead of multiple

    def test_connection_kwargs(self):
        """A spot check to make sure optional connection kwargs gets passed to connection"""
        cache = GridFSDict(
            'test',
            host='mongodb://0.0.0.0',
            port=2222,
            tz_aware=True,
            connect=False,
            invalid_kwarg='???',
        )
        assert "host=['0.0.0.0:2222']" in repr(cache.connection)
        assert "tz_aware=True" in repr(cache.connection)

    def test_corrupt_file(self):
        """A corrupted file should be handled and raise a KeyError instead"""
        from gridfs import GridFS
        from gridfs.errors import CorruptGridFile

        cache = self.init_cache()
        cache['key'] = 'value'
        with pytest.raises(KeyError), patch.object(GridFS, 'find_one', side_effect=CorruptGridFile):
            cache['key']

    def test_file_exists(self):
        from gridfs import GridFS
        from gridfs.errors import FileExists

        cache = self.init_cache()

        # This write should just quiety fail
        with patch.object(GridFS, 'put', side_effect=FileExists):
            cache['key'] = 'value_1'

        assert 'key' not in cache


class TestGridFSCache(BaseCacheTest):
    backend_class = GridFSCache
