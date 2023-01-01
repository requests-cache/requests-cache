from unittest.mock import patch

import pytest
from redis import StrictRedis

from requests_cache.backends import RedisCache, RedisDict, RedisHashDict
from tests.conftest import fail_if_no_connection, httpbin
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
    init_kwargs = {'serializer': 'pickle'}


class TestRedisCache(BaseCacheTest):
    backend_class = RedisCache

    @patch.object(StrictRedis, 'setex')
    def test_ttl(self, mock_setex):
        session = self.init_session(expire_after=60)
        session.get(httpbin('get'))
        call_args = mock_setex.mock_calls[0][1]
        assert call_args[1] == 3660  # Should be expiration + default offset

    @patch.object(StrictRedis, 'setex')
    def test_ttl__offset(self, mock_setex):
        session = self.init_session(expire_after=60, ttl_offset=500)
        session.get(httpbin('get'))
        call_args = mock_setex.mock_calls[0][1]
        assert call_args[1] == 560  # Should be expiration + custom offset

    @patch.object(StrictRedis, 'setex')
    @patch.object(StrictRedis, 'set')
    def test_ttl__disabled(self, mock_set, mock_setex):
        session = self.init_session(expire_after=60, ttl=False)
        session.get(httpbin('get'))
        mock_setex.assert_not_called()
        mock_set.assert_called()
