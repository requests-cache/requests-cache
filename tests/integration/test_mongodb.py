from unittest.mock import patch

import pytest
from pymongo import MongoClient

from requests_cache._utils import get_valid_kwargs
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

    @patch('requests_cache.backends.mongodb.MongoClient')
    @patch(
        'requests_cache.backends.mongodb.get_valid_kwargs',
        side_effect=lambda cls, kwargs: get_valid_kwargs(MongoClient, kwargs),
    )
    def test_connection_kwargs(self, mock_get_valid_kwargs, mock_client):
        """A spot check to make sure optional connection kwargs gets passed to connection"""
        MongoDict('test', host='http://0.0.0.0', port=1234, invalid_kwarg='???')
        mock_client.assert_called_with(host='http://0.0.0.0', port=1234)


class TestMongoCache(BaseCacheTest):
    backend_class = MongoCache


class TestGridFSPickleDict(BaseStorageTest):
    storage_class = GridFSPickleDict
    picklable = True
    num_instances = 1  # Only test a single collecton instead of multiple

    @patch('requests_cache.backends.gridfs.GridFS')
    @patch('requests_cache.backends.gridfs.MongoClient')
    @patch(
        'requests_cache.backends.gridfs.get_valid_kwargs',
        side_effect=lambda cls, kwargs: get_valid_kwargs(MongoClient, kwargs),
    )
    def test_connection_kwargs(self, mock_get_valid_kwargs, mock_client, mock_gridfs):
        """A spot check to make sure optional connection kwargs gets passed to connection"""
        GridFSPickleDict('test', host='http://0.0.0.0', port=1234, invalid_kwarg='???')
        mock_client.assert_called_with(host='http://0.0.0.0', port=1234)


class TestGridFSCache(BaseCacheTest):
    backend_class = GridFSCache
