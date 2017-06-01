#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    requests_cache.backends.dynamodb
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    ``dynamodb`` cache backend
"""
from .base import BaseCache
from .storage.dynamodbdict import DynamoDbDict


class DynamoDbCache(BaseCache):
    """ ``dynamodb`` cache backend.
    """
    def __init__(self, table_name='requests-cache', **options):
        """
        :param namespace: dynamodb table name (default: ``'requests-cache'``)
        :param connection: (optional) ``boto3.resource('dynamodb')``
        """
        super(DynamoDbCache, self).__init__(**options)
        self.responses = DynamoDbDict(table_name, 'responses',
                                      options.get('connection'),
                                      options.get('endpont_url'),
                                      options.get('region_name'),
                                      options.get('read_capacity_units'),
                                      options.get('write_capacity_units'))
        self.keys_map = DynamoDbDict(table_name,
                                     'urls',
                                     self.responses.connection)
