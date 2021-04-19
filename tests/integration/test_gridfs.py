import pytest
import unittest
from unittest.mock import patch

from pymongo import MongoClient

from requests_cache.backends import GridFSPickleDict, get_valid_kwargs
from tests.conftest import fail_if_no_connection
from tests.integration.test_backends import BaseStorageTestCase


@pytest.fixture(scope='module', autouse=True)
@fail_if_no_connection
def ensure_connection():
    """Fail all tests in this module if MongoDB is not running"""
    from pymongo import MongoClient

    client = MongoClient(serverSelectionTimeoutMS=200)
    client.server_info()


class GridFSPickleDictTestCase(BaseStorageTestCase, unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, storage_class=GridFSPickleDict, picklable=True, **kwargs)

    def test_set_get(self):
        """Override base test to test a single collecton instead of multiple"""
        d1 = self.storage_class(self.NAMESPACE, self.TABLES[0])
        d1[1] = 1
        d1[2] = 2
        assert list(d1.keys()) == [1, 2]

        with pytest.raises(KeyError):
            d1[4]


@patch('requests_cache.backends.gridfs.GridFS')
@patch('requests_cache.backends.gridfs.MongoClient')
@patch(
    'requests_cache.backends.gridfs.get_valid_kwargs',
    side_effect=lambda cls, kwargs: get_valid_kwargs(MongoClient, kwargs),
)
def test_connection_kwargs(mock_get_valid_kwargs, mock_client, mock_gridfs):
    """A spot check to make sure optional connection kwargs gets passed to connection"""
    GridFSPickleDict('test', host='http://0.0.0.0', port=1234, invalid_kwarg='???')
    mock_client.assert_called_with(host='http://0.0.0.0', port=1234)
