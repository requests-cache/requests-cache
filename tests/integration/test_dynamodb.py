from collections import OrderedDict
from decimal import Decimal
from unittest.mock import patch

import pytest
from botocore.exceptions import ClientError

from requests_cache.backends import DynamoDbCache, DynamoDbDict
from requests_cache.serializers import dynamodb_document_serializer
from tests.conftest import HTTPBIN_FORMATS, HTTPBIN_METHODS, fail_if_no_connection
from tests.integration.base_cache_test import TEST_SERIALIZERS, BaseCacheTest
from tests.integration.base_storage_test import BaseStorageTest

AWS_OPTIONS = {
    'endpoint_url': 'http://localhost:8000',
    'region_name': 'us-east-1',
    'aws_access_key_id': 'placeholder',
    'aws_secret_access_key': 'placeholder',
}
DYNAMODB_OPTIONS = {
    **AWS_OPTIONS,
    'serializer': None,  # Use class default serializer
}

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
    init_kwargs = DYNAMODB_OPTIONS

    @patch('requests_cache.backends.dynamodb.boto3.resource')
    def test_connection_kwargs(self, mock_resource):
        """A spot check to make sure optional connection kwargs gets passed to connection"""
        DynamoDbDict('test_table', 'namespace', region_name='us-east-2', invalid_kwarg='???')
        mock_resource.assert_called_with('dynamodb', region_name='us-east-2')

    def test_create_table_error(self):
        """An error other than 'table already exists' should be reraised"""
        cache = self.init_cache()
        error = ClientError({'Error': {'Code': 'NullPointerException'}}, 'CreateTable')
        with patch.object(cache.connection.meta.client, 'update_time_to_live', side_effect=error):
            with pytest.raises(ClientError):
                cache._enable_ttl()

    def test_enable_ttl_error(self):
        """An error other than 'ttl already enabled' should be reraised"""
        cache = self.init_cache()
        error = ClientError({'Error': {'Code': 'NullPointerException'}}, 'CreateTable')
        with patch.object(cache.connection, 'create_table', side_effect=error):
            with pytest.raises(ClientError):
                cache._create_table()

    @pytest.mark.parametrize('ttl_enabled', [True, False])
    def test_ttl(self, ttl_enabled):
        """DynamoDB's TTL removal process can take up to 48 hours to run, so just test if the
        'ttl' attribute is set correctly if enabled, and not set if disabled.
        """
        cache = self.init_cache(ttl=ttl_enabled)
        item = OrderedDict(foo='bar')
        item.expires_unix = 60
        cache['key'] = item

        # 'ttl' is a reserved word, so to retrieve it we need to alias it
        item = cache._table.get_item(
            Key=cache._composite_key('key'),
            ProjectionExpression='#t',
            ExpressionAttributeNames={'#t': 'ttl'},
        )
        ttl_value = item['Item'].get('ttl')

        if ttl_enabled:
            assert isinstance(ttl_value, Decimal)
        else:
            assert ttl_value is None


class TestDynamoDbCache(BaseCacheTest):
    backend_class = DynamoDbCache
    init_kwargs = DYNAMODB_OPTIONS

    @pytest.mark.parametrize('serializer', DYNAMODB_SERIALIZERS)
    @pytest.mark.parametrize('method', HTTPBIN_METHODS)
    @pytest.mark.parametrize('field', ['params', 'data', 'json'])
    def test_all_methods(self, field, method, serializer):
        super().test_all_methods(field, method, serializer)

    @pytest.mark.parametrize('serializer', DYNAMODB_SERIALIZERS)
    @pytest.mark.parametrize('response_format', HTTPBIN_FORMATS)
    def test_all_response_formats(self, response_format, serializer):
        super().test_all_response_formats(response_format, serializer)
