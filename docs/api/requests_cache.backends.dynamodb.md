# DynamoDB
```{image} ../_static/dynamodb.png
```

[DynamoDB](https://aws.amazon.com/dynamodb) highly scalable NoSQL document database hosted on
[Amazon Web Services](https://aws.amazon.com).

## Use Cases
In terms of features, DynamoDB is roughly comparable to MongoDB and other NoSQL databases. It is a
fully managed service, making it very convenient to use if you are already on AWS. It is an
especially good fit for serverless applications running on
[AWS Lambda](https://aws.amazon.com/lambda).

```{warning}
DynamoDB item sizes are limited to 400KB. If you need to cache larger responses, consider
using a different backend.
```

## Creating Tables
Tables will be automatically created if they don't already exist. This is convienient if you just
want to quickly test out DynamoDB as a cache backend, but in a production environment you will
likely want to create the tables yourself, for example with [CloudFormation](https://aws.amazon.com/cloudformation/) or [Terraform](https://www.terraform.io/). Here are the
details you'll need:

- Tables: two tables, named `responses` and `redirects`
- Partition key (aka namespace): `namespace`
- Range key (aka sort key): `key`
- Attributes: `namespace` (string) and `key` (string)

## Connection Options
The DynamoDB backend accepts any keyword arguments for {py:meth}`boto3.session.Session.resource`.
These can be passed via {py:class}`.DynamoDbCache`:
```python
>>> backend = DynamoDbCache(region_name='us-west-2')
>>> session = CachedSession('http_cache', backend=backend)
```

## API Reference
```{eval-rst}
.. automodsumm:: requests_cache.backends.dynamodb
   :classes-only:
   :nosignatures:

.. automodule:: requests_cache.backends.dynamodb
   :members:
   :undoc-members:
   :inherited-members:
   :show-inheritance:
```
