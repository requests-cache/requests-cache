import pytest
import unittest
from unittest.mock import patch

from requests_cache.backends.redis import RedisCache, RedisDict
from tests.conftest import fail_if_no_connection
from tests.integration.test_backends import BaseStorageTestCase


@pytest.fixture(scope='module', autouse=True)
@fail_if_no_connection
def ensure_connection():
    """Fail all tests in this module if Redis is not running"""
    from redis import Redis

    Redis().info()


class RedisTestCase(BaseStorageTestCase, unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, storage_class=RedisDict, picklable=True, **kwargs)


# @patch.object(Redis, '__init__', Redis.__init__)
@patch('requests_cache.backends.redis.StrictRedis')
def test_connection_kwargs(mock_redis):
    """A spot check to make sure optional connection kwargs gets passed to connection"""
    RedisCache('test', username='user', password='pass', invalid_kwarg='???')
    mock_redis.assert_called_with(username='user', password='pass')
