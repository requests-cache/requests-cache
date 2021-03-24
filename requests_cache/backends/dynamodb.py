import boto3
from botocore.exceptions import ClientError

from .base import BaseCache, BaseStorage


class DynamoDbCache(BaseCache):
    """`DynamoDB cache backend"""

    def __init__(self, table_name='http_cache', **kwargs):
        """
        :param namespace: dynamodb table name (default: ``'requests-cache'``)
        :param connection: (optional) ``boto3.resource('dynamodb')``
        """
        super().__init__(**kwargs)
        self.responses = DynamoDbDict(table_name, namespace='responses', **kwargs)
        kwargs['connection'] = self.responses.connection
        self.redirects = DynamoDbDict(table_name, namespace='redirects', **kwargs)


class DynamoDbDict(BaseStorage):
    """A dictionary-like interface for DynamoDB key-value store"""

    def __init__(
        self,
        table_name,
        namespace='http_cache',
        connection=None,
        endpoint_url=None,
        region_name='us-east-1',
        read_capacity_units=1,
        write_capacity_units=1,
        **kwargs,
    ):

        """
        The actual key name on the dynamodb server will be
        ``namespace``:``namespace_name``

        In order to deal with how dynamodb stores data/keys,
        everything, i.e. keys and data, must be pickled.

        :param table_name: table name to use
        :param namespace_name: name of the hash map stored in dynamodb
                                (default: dynamodb_dict_data)
        :param connection: ``boto3.resource('dynamodb')`` instance.
                           If it's ``None`` (default), a new connection with
                           default options will be created
        :param endpoint_url: url of dynamodb server.

        """
        super().__init__(**kwargs)
        self._self_key = namespace
        if connection is not None:
            self.connection = connection
        else:
            self.connection = boto3.resource('dynamodb', endpoint_url=endpoint_url, region_name=region_name)
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

    def __getitem__(self, key):
        composite_key = {'namespace': self._self_key, 'key': str(key)}
        result = self._table.get_item(Key=composite_key)
        if 'Item' not in result:
            raise KeyError
        return self.deserialize(result['Item']['value'].value)

    def __setitem__(self, key, item):
        item = {'namespace': self._self_key, 'key': str(key), 'value': self.serialize(item)}
        self._table.put_item(Item=item)

    def __delitem__(self, key):
        composite_key = {'namespace': self._self_key, 'key': str(key)}
        response = self._table.delete_item(Key=composite_key, ReturnValues='ALL_OLD')
        if 'Attributes' not in response:
            raise KeyError

    def __len__(self):
        return self.__count_table()

    def __iter__(self):
        response = self.__scan_table()
        for v in response['Items']:
            yield self.deserialize(v['value'].value)

    def clear(self):
        response = self.__scan_table()
        for v in response['Items']:
            composite_key = {'namespace': v['namespace'], 'key': v['key']}
            self._table.delete_item(Key=composite_key)

    def __str__(self):
        return str(dict(self.items()))

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
