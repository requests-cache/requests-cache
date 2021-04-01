#!/usr/bin/env python
import os
import unittest

from tests.integration.test_backends import BaseBackendTestCase

try:
    from requests_cache.backends.dynamodb import DynamoDbDict
except ImportError:
    print("DynamoDb not installed")
else:
    # boto3 will accept any values for creds, but they still need to be present
    os.environ['AWS_ACCESS_KEY_ID'] = 'placeholder'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'placeholder'

    class DynamoDbDictWrapper(DynamoDbDict):
        def __init__(self, namespace, collection_name='dynamodb_dict_data', **options):
            options['endpoint_url'] = 'http://0.0.0.0:8000'
            super().__init__(namespace, collection_name, **options)

    class DynamoDbTestCase(BaseBackendTestCase, unittest.TestCase):
        dict_class = DynamoDbDictWrapper
        pickled_dict_class = DynamoDbDictWrapper

    if __name__ == '__main__':
        unittest.main()
