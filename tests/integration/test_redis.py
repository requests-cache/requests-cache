import pytest
import unittest

from requests_cache.backends.redis import RedisDict
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
