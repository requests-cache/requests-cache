#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Path hack
import os, sys
sys.path.insert(0, os.path.abspath('..'))

try:
    import unittest2 as unittest
except ImportError:
    import unittest

from tests.test_custom_dict import BaseCustomDictTestCase
try:
    from requests_cache.backends.storage.dynamodbdict import DynamoDbDict
except ImportError:
    print("DynamoDb not installed")
else:

    class WrapDynamoDbDict(DynamoDbDict):
        def __init__(self, namespace, collection_name='dynamodb_dict_data', **options):
            options['endpoint_url'] = os.environ['DYNAMODB_ENDPOINT_URL'] if 'DYNAMODB_ENDPOINT_URL' in os.environ else None
            super(WrapDynamoDbDict,self).__init__( namespace, collection_name, **options)

    class DynamoDbDictTestCase(BaseCustomDictTestCase, unittest.TestCase):
        dict_class = WrapDynamoDbDict
        pickled_dict_class = WrapDynamoDbDict

    if __name__ == '__main__':
        unittest.main()
