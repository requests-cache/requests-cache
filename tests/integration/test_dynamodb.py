from unittest.mock import patch

import pytest

from requests_cache.backends import DynamoDbCache, DynamoDbDict, DynamoDocumentDict
from requests_cache.serializers import dynamodb_document_serializer
from tests.conftest import AWS_OPTIONS, HTTPBIN_FORMATS, HTTPBIN_METHODS, fail_if_no_connection
from tests.integration.base_cache_test import TEST_SERIALIZERS, BaseCacheTest
from tests.integration.base_storage_test import BaseStorageTest

# Add extra DynamoDB-specific format to list of serializers to test against
DYNAMODB_SERIALIZERS = [dynamodb_document_serializer] + list(TEST_SERIALIZERS.values())


@pytest.fixture(scope='module', autouse=True)
@fail_if_no_connection(connect_timeout=5)
def ensure_connection():
    """Fail all tests in this module if DynamoDB is not running"""
    import boto3

    client = boto3.client('dynamodb', **AWS_OPTIONS)
    client.describe_limits()


class TestDynamoDbDict(BaseStorageTest):
    storage_class = DynamoDbDict
    init_kwargs = AWS_OPTIONS

    @patch('requests_cache.backends.dynamodb.boto3.resource')
    def test_connection_kwargs(self, mock_resource):
        """A spot check to make sure optional connection kwargs gets passed to connection"""
        DynamoDbDict('test_table', 'namespace', region_name='us-east-2', invalid_kwarg='???')
        mock_resource.assert_called_with('dynamodb', region_name='us-east-2')


class TestDynamoDocumentDict(BaseStorageTest):
    storage_class = DynamoDocumentDict
    init_kwargs = AWS_OPTIONS
    picklable = True


class TestDynamoDbCache(BaseCacheTest):
    backend_class = DynamoDbCache
    init_kwargs = {
        'serializer': None,
        **AWS_OPTIONS,
    }  # Use class default serializer instead of pickle

    @pytest.mark.parametrize('serializer', DYNAMODB_SERIALIZERS)
    @pytest.mark.parametrize('method', HTTPBIN_METHODS)
    @pytest.mark.parametrize('field', ['params', 'data', 'json'])
    def test_all_methods(self, field, method, serializer):
        super().test_all_methods(field, method, serializer)

    @pytest.mark.parametrize('serializer', DYNAMODB_SERIALIZERS)
    @pytest.mark.parametrize('response_format', HTTPBIN_FORMATS)
    def test_all_response_formats(self, response_format, serializer):
        super().test_all_response_formats(response_format, serializer)
