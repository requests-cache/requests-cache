import pytest
import unittest

from requests_cache.backends import DynamoDbDict
from tests.conftest import fail_if_no_connection
from tests.integration.test_backends import BaseBackendTestCase

boto_options = {
    'endpoint_url': 'http://localhost:8000',
    'region_name': 'us-east-1',
    'aws_access_key_id': 'placeholder',
    'aws_secret_access_key': 'placeholder',
}


@pytest.fixture(scope='module', autouse=True)
@fail_if_no_connection
def ensure_connection():
    """Fail all tests in this module if DynamoDB is not running"""
    import boto3

    client = boto3.client('dynamodb', **boto_options)
    client.describe_limits()


class DynamoDbDictWrapper(DynamoDbDict):
    def __init__(self, namespace, collection_name='dynamodb_dict_data', **options):
        options.update(boto_options)
        super().__init__(namespace, collection_name, **options)


class DynamoDbTestCase(BaseBackendTestCase, unittest.TestCase):
    dict_class = DynamoDbDictWrapper
    pickled_dict_class = DynamoDbDictWrapper
