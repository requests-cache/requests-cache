import pytest
import unittest
from unittest.mock import patch

from pymongo import MongoClient

from requests_cache.backends import MongoDict, MongoPickleDict, get_valid_kwargs
from tests.conftest import fail_if_no_connection
from tests.integration.test_backends import BaseStorageTestCase


@pytest.fixture(scope='module', autouse=True)
@fail_if_no_connection
def ensure_connection():
    """Fail all tests in this module if MongoDB is not running"""
    from pymongo import MongoClient

    client = MongoClient(serverSelectionTimeoutMS=200)
    client.server_info()


class MongoDictTestCase(BaseStorageTestCase, unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, storage_class=MongoDict, **kwargs)


class MongoPickleDictTestCase(BaseStorageTestCase, unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, storage_class=MongoPickleDict, picklable=True, **kwargs)


@patch('requests_cache.backends.mongo.MongoClient')
@patch(
    'requests_cache.backends.mongo.get_valid_kwargs',
    side_effect=lambda cls, kwargs: get_valid_kwargs(MongoClient, kwargs),
)
def test_connection_kwargs(mock_get_valid_kwargs, mock_client):
    """A spot check to make sure optional connection kwargs gets passed to connection"""
    MongoDict('test', host='http://0.0.0.0', port=1234, invalid_kwarg='???')
    mock_client.assert_called_with(host='http://0.0.0.0', port=1234)
