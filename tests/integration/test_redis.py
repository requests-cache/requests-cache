from unittest.mock import patch

import pytest

from requests_cache.backends.redis import RedisCache, RedisDict, RedisHashDict
from tests.conftest import fail_if_no_connection
from tests.integration.base_cache_test import BaseCacheTest
from tests.integration.base_storage_test import BaseStorageTest


@pytest.fixture(scope='module', autouse=True)
@fail_if_no_connection()
def ensure_connection():
    """Fail all tests in this module if Redis is not running"""
    from redis import Redis

    Redis().info()


class TestRedisDict(BaseStorageTest):
    storage_class = RedisDict
    num_instances = 1  # Only supports a single instance, since it stores items under top-level keys

    @patch('requests_cache.backends.redis.StrictRedis')
    def test_connection_kwargs(self, mock_redis):
        """A spot check to make sure optional connection kwargs get passed to connection"""
        RedisCache('test', username='user', password='pass', invalid_kwarg='???')
        mock_redis.assert_called_with(username='user', password='pass')


class TestRedisHashDict(TestRedisDict):
    storage_class = RedisHashDict
    num_instances: int = 10  # Supports multiple instances, since this stores items under hash keys
    picklable = True


class TestRedisCache(BaseCacheTest):
    backend_class = RedisCache
