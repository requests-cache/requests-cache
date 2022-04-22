from unittest.mock import patch

import pytest
from gridfs import GridFS
from gridfs.errors import CorruptGridFile, FileExists

from requests_cache.backends import (
    GridFSCache,
    GridFSPickleDict,
    MongoCache,
    MongoDict,
    MongoPickleDict,
)
from tests.conftest import fail_if_no_connection
from tests.integration.base_cache_test import BaseCacheTest
from tests.integration.base_storage_test import BaseStorageTest


@pytest.fixture(scope='module', autouse=True)
@fail_if_no_connection()
def ensure_connection():
    """Fail all tests in this module if MongoDB is not running"""
    from pymongo import MongoClient

    client = MongoClient(serverSelectionTimeoutMS=200)
    client.server_info()


class TestMongoDict(BaseStorageTest):
    storage_class = MongoDict


class TestMongoPickleDict(BaseStorageTest):
    storage_class = MongoPickleDict
    picklable = True

    def test_connection_kwargs(self):
        """A spot check to make sure optional connection kwargs get passed to connection"""
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


class TestGridFSPickleDict(BaseStorageTest):
    storage_class = GridFSPickleDict
    picklable = True
    num_instances = 1  # Only test a single collecton instead of multiple

    def test_connection_kwargs(self):
        """A spot check to make sure optional connection kwargs get passed to connection"""
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

    def test_corrupt_file(self):
        """A corrupted file should be handled and raise a KeyError instead"""
        cache = self.init_cache()
        cache['key'] = 'value'
        with pytest.raises(KeyError), patch.object(GridFS, 'find_one', side_effect=CorruptGridFile):
            cache['key']

    def test_file_exists(self):
        cache = self.init_cache()

        # This write should just quiety fail
        with patch.object(GridFS, 'put', side_effect=FileExists):
            cache['key'] = 'value_1'

        assert 'key' not in cache


class TestGridFSCache(BaseCacheTest):
    backend_class = GridFSCache
