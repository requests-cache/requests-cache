import pytest
import unittest

from requests_cache.backends.redis import RedisDict
from tests.conftest import fail_if_no_connection
from tests.integration.test_backends import BaseBackendTestCase


@pytest.fixture(scope='module', autouse=True)
@fail_if_no_connection
def ensure_connection():
    """Fail all tests in this module if Redis is not running"""
    from redis import Redis

    Redis().info()


class RedisTestCase(BaseBackendTestCase, unittest.TestCase):
    dict_class = RedisDict
    pickled_dict_class = RedisDict
