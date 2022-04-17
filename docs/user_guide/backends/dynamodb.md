(dynamodb)=
# DynamoDB
```{image} ../../_static/dynamodb.png
```

[DynamoDB](https://aws.amazon.com/dynamodb) is a fully managed, highly scalable NoSQL document
database hosted on [Amazon Web Services](https://aws.amazon.com).

## Use Cases
In terms of features, DynamoDB is roughly comparable to MongoDB and other NoSQL databases. Since
it's a managed service, no server setup or maintenance is required, and it's very convenient to use
if your application is already on AWS. It is an especially good fit for serverless applications
running on [AWS Lambda](https://aws.amazon.com/lambda).

```{warning}
DynamoDB item sizes are limited to 400KB. If you need to cache larger responses, consider
using a different backend.
```

## Usage Example
Initialize with a {py:class}`.DynamoDbCache` instance:
```python
>>> from requests_cache import CachedSession, DynamoDbCache
>>> session = CachedSession(backend=DynamoDbCache())
```

Or by alias:
```python
>>> session = CachedSession(backend='dynamodb')
```

## Connection Options
This backend accepts any keyword arguments for {py:meth}`boto3.session.Session.resource`:
```python
>>> backend = DynamoDbCache(region_name='us-west-2')
>>> session = CachedSession(backend=backend)
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
