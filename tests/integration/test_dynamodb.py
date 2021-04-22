import pytest
from unittest.mock import patch

from requests_cache.backends import DynamoDbCache, DynamoDbDict
from tests.conftest import AWS_OPTIONS, fail_if_no_connection
from tests.integration.base_cache_test import BaseCacheTest
from tests.integration.base_storage_test import BaseStorageTest

# Run this test module last, since the DynamoDB container takes the longest to initialize
pytestmark = pytest.mark.order(-1)


@pytest.fixture(scope='module', autouse=True)
@fail_if_no_connection
def ensure_connection():
    """Fail all tests in this module if DynamoDB is not running"""
    import boto3

    client = boto3.client('dynamodb', **AWS_OPTIONS)
    client.describe_limits()


class TestDynamoDbDict(BaseStorageTest):
    storage_class = DynamoDbDict
    init_kwargs = AWS_OPTIONS
    picklable = True

    @patch('requests_cache.backends.dynamodb.boto3.resource')
    def test_connection_kwargs(self, mock_resource):
        """A spot check to make sure optional connection kwargs gets passed to connection"""
        DynamoDbDict('test', region_name='us-east-2', invalid_kwarg='???')
        mock_resource.assert_called_with('dynamodb', region_name='us-east-2')


class TestDynamoDbCache(BaseCacheTest):
    backend_class = DynamoDbCache
    init_kwargs = AWS_OPTIONS
