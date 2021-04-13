import boto3
from botocore.exceptions import ClientError

from .base import BaseCache, BaseStorage


class DynamoDbCache(BaseCache):
    """DynamoDB cache backend

    Args:
        table_name: DynamoDb table name
        namespace: Name of DynamoDb hash map
        connection: DynamoDb Resource object (``boto3.resource('dynamodb')``) to use instead of
            creating a new one
    """

    def __init__(self, table_name='http_cache', **kwargs):
        super().__init__(**kwargs)
        self.responses = DynamoDbDict(table_name, namespace='responses', **kwargs)
        kwargs['connection'] = self.responses.connection
        self.redirects = DynamoDbDict(table_name, namespace='redirects', **kwargs)


class DynamoDbDict(BaseStorage):
    """A dictionary-like interface for DynamoDB key-value store

    **Note:** The actual key name on the dynamodb server will be ``namespace``:``table_name``

    In order to deal with how dynamodb stores data/keys,
    everything, i.e. keys and data, must be pickled.

    Args:
        table_name: DynamoDb table name
        namespace: Name of DynamoDb hash map
        connection: DynamoDb Resource object (``boto3.resource('dynamodb')``) to use instead of
            creating a new one
        endpoint_url: Alternative URL of dynamodb server.
    """

    def __init__(
        self,
        table_name,
        namespace='http_cache',
        connection=None,
        endpoint_url=None,
        region_name='us-east-1',
        aws_access_key_id=None,
        aws_secret_access_key=None,
        read_capacity_units=1,
        write_capacity_units=1,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._self_key = namespace
        if connection is not None:
            self.connection = connection
        else:
            # TODO: Use inspection to get any valid resource arguments from **kwargs
            self.connection = boto3.resource(
                'dynamodb',
                endpoint_url=endpoint_url,
                region_name=region_name,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
            )

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
