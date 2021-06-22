import pytest
from unittest.mock import patch

from requests_cache.backends.redis import RedisCache, RedisDict
from tests.conftest import fail_if_no_connection
from tests.integration.base_cache_test import BaseCacheTest
from tests.integration.base_storage_test import BaseStorageTest


@pytest.fixture(scope='module', autouse=True)
@fail_if_no_connection
def ensure_connection():
    """Fail all tests in this module if Redis is not running"""
    from redis import Redis

    Redis().info()


class TestRedisDict(BaseStorageTest):
    storage_class = RedisDict
    picklable = True

    @patch('requests_cache.backends.redis.StrictRedis')
    def test_connection_kwargs(self, mock_redis):
        """A spot check to make sure optional connection kwargs get passed to connection"""
        RedisCache('test', username='user', password='pass', invalid_kwarg='???')
        mock_redis.assert_called_with(username='user', password='pass')


class TestRedisCache(BaseCacheTest):
    backend_class = RedisCache
