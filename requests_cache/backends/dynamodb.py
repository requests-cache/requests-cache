"""
.. image::
    ../_static/dynamodb.png

`DynamoDB <https://aws.amazon.com/dynamodb>`_ is a NoSQL document database hosted on `Amazon Web
Services <https://aws.amazon.com>`_. In terms of features and use cases, it is roughly comparable to
MongoDB and other NoSQL databases. It is an especially good fit for serverless applications running
on `AWS Lambda <https://aws.amazon.com/lambda>`_.

.. warning::
    DynamoDB binary item sizes are limited to 400KB. If you need to cache larger responses, consider
    using a different backend.

Connection Options
^^^^^^^^^^^^^^^^^^
The DynamoDB backend accepts any keyword arguments for :py:meth:`boto3.session.Session.resource`.
These can be passed via :py:class:`.CachedSession`:

    >>> session = CachedSession('http_cache', backend='dynamodb', region_name='us-west-2')

Or via :py:class:`.DynamoDbCache`:

    >>> backend = DynamoDbCache(region_name='us-west-2')
    >>> session = CachedSession('http_cache', backend=backend)

API Reference
^^^^^^^^^^^^^
.. automodsumm:: requests_cache.backends.dynamodb
   :classes-only:
   :nosignatures:
"""
from typing import Dict, Iterable

import boto3
from boto3.dynamodb.types import Binary
from boto3.resources.base import ServiceResource
from botocore.exceptions import ClientError

from . import BaseCache, BaseStorage, get_valid_kwargs


class DynamoCache(BaseCache):
    """DynamoDB cache backend

    Args:
        table_name: DynamoDB table name
        namespace: Name of DynamoDB hash map
        connection: :boto3:`DynamoDB Resource <services/dynamodb.html#DynamoDB.ServiceResource>`
            object to use instead of creating a new one
        kwargs: Additional keyword arguments for :py:meth:`~boto3.session.Session.resource`
    """

    def __init__(self, table_name: str = 'http_cache', connection: ServiceResource = None, **kwargs):
        super().__init__(**kwargs)
        self.responses = DynamoDict(table_name, 'responses', connection=connection, **kwargs)
        self.redirects = DynamoDict(
            table_name, 'redirects', connection=self.responses.connection, **kwargs
        )


class DynamoDict(BaseStorage):
    """A dictionary-like interface for DynamoDB key-value store

    **Notes:**
        * The actual table name on the Dynamodb server will be ``namespace:table_name``
        * In order to deal with how DynamoDB stores data, all values are serialized.

    Args:
        table_name: DynamoDB table name
        namespace: Name of DynamoDB hash map
        connection: :boto3:`DynamoDB Resource <services/dynamodb.html#DynamoDB.ServiceResource>`
            object to use instead of creating a new one
        kwargs: Additional keyword arguments for :py:meth:`~boto3.session.Session.resource`
    """

    def __init__(
        self,
        table_name,
        namespace='http_cache',
        connection=None,
        read_capacity_units=1,
        write_capacity_units=1,
        **kwargs,
    ):
        super().__init__(**kwargs)
        connection_kwargs = get_valid_kwargs(boto3.Session, kwargs, extras=['endpoint_url'])
        self.connection = connection or boto3.resource('dynamodb', **connection_kwargs)
        self._self_key = namespace

        try:
            self.connection.create_table(
                AttributeDefinitions=[
                    {
                        'AttributeName': 'namespace',
                        'AttributeType': 'S',
                    },
                    {
                        'AttributeName': 'key',
                        'AttributeType': 'S',
                    },
                ],
                TableName=table_name,
                KeySchema=[
                    {'AttributeName': 'namespace', 'KeyType': 'HASH'},
                    {'AttributeName': 'key', 'KeyType': 'RANGE'},
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': read_capacity_units,
                    'WriteCapacityUnits': write_capacity_units,
                },
            )
        except ClientError:
            pass
        self._table = self.connection.Table(table_name)
        self._table.wait_until_exists()

    def composite_key(self, key: str) -> Dict[str, str]:
        return {'namespace': self._self_key, 'key': str(key)}

    def __getitem__(self, key):
        result = self._table.get_item(Key=self.composite_key(key))
        if 'Item' not in result:
            raise KeyError

        # Depending on the serializer, the value may be either a string or Binary object
        raw_value = result['Item']['value']
        return self.serializer.loads(raw_value.value if isinstance(raw_value, Binary) else raw_value)

    def __setitem__(self, key, value):
        item = {**self.composite_key(key), 'value': self.serializer.dumps(value)}
        self._table.put_item(Item=item)

    def __delitem__(self, key):
        response = self._table.delete_item(Key=self.composite_key(key), ReturnValues='ALL_OLD')
        if 'Attributes' not in response:
            raise KeyError

    def __len__(self):
        return self.__count_table()

    def __iter__(self):
        response = self.__scan_table()
        for v in response['Items']:
            yield v['key']

    def bulk_delete(self, keys: Iterable[str]):
        """Delete multiple keys from the cache. Does not raise errors for missing keys."""
        with self._table.batch_writer() as batch:
            for key in keys:
                batch.delete_item(Key=self.composite_key(key))

    def clear(self):
        response = self.__scan_table()
        for v in response['Items']:
            composite_key = {'namespace': v['namespace'], 'key': v['key']}
            self._table.delete_item(Key=composite_key)

    def __scan_table(self):
        expression_attribute_values = {':Namespace': self._self_key}
        expression_attribute_names = {'#N': 'namespace'}
        key_condition_expression = '#N = :Namespace'
        return self._table.query(
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names,
            KeyConditionExpression=key_condition_expression,
        )

    def __count_table(self):
        expression_attribute_values = {':Namespace': self._self_key}
        expression_attribute_names = {'#N': 'namespace'}
        key_condition_expression = '#N = :Namespace'
        return self._table.query(
            Select='COUNT',
            ExpressionAttributeValues=expression_attribute_values,
            ExpressionAttributeNames=expression_attribute_names,
            KeyConditionExpression=key_condition_expression,
        )['Count']
