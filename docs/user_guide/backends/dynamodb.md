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

## Viewing Responses
By default, responses are only partially serialized so they can be saved as plain DynamoDB
documents. Response data can then be easily viewed via the
[AWS Console](https://aws.amazon.com/console/).

Here is an example of responses listed under **DynamoDB > Tables > Explore Items:**
:::{dropdown} Screenshot
:animate: fade-in-slide-down
:color: primary
:icon: file-media

```{image} ../../_static/dynamodb_items.png
```
:::

And here is an example response:
:::{dropdown} Screenshot
:animate: fade-in-slide-down
:color: primary
:icon: file-media

```{image} ../../_static/dynamodb_response.png
```
:::

It is also possible query these responses with the [AWS CLI](https://aws.amazon.com/cli), for
example:
```bash
aws dynamodb query --table-name http_cache > responses.json
```

```bash
aws dynamodb query \
    --table-name http_cache \
    --key-condition-expression "namespace = :n1" \
    --expression-attribute-values '{":n1": {"S": "responses"}}' \
    > responses.json
```

## Expiration
DynamoDB natively supports TTL on a per-item basis, and can automatically remove expired responses from
the cache. This will be set by by default, according to normal {ref}`expiration settings <expiration>`.

```{warning}
DynamoDB does not remove expired items immediately. See
[How It Works: DynamoDB Time to Live](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/howitworks-ttl.html)
for more details.
```

If needed, you can disable this behavior with the `ttl` argument:
```python
>>> backend = DynamoDbCache(ttl=False)
```

## Creating a Table
A table will be automatically created if one doesn't already exist. This is convienient if you just
want to quickly test out DynamoDB as a cache backend, but in a production environment you will
likely want to create the tables yourself, for example with
[CloudFormation](https://aws.amazon.com/cloudformation/) or [Terraform](https://www.terraform.io/).

You just need a table with a single partition key. A `value` attribute (containing response data)
will be created dynamically once items are added to the table.
- Table: `http_cache` (or any other name, as long as it matches the `table_name` parameter for `DynamoDbCache`)
- Attributes:
  - `key`: String
- Keys:
  - Partition key (aka hash key): `key`

Example of manually creating a table in the console:
:::{dropdown} Screenshot
:animate: fade-in-slide-down
:color: primary
:icon: file-media

```{image} ../../_static/dynamodb_create_table.png
```
:::

### Example CloudFormation Template
:::{dropdown} Example
:animate: fade-in-slide-down
:color: primary
:icon: file-code

[cloudformation.yml](https://github.com/requests-cache/requests-cache/blob/main/examples/cloudformation.yml)
```{literalinclude} ../../../examples/cloudformation.yml
:language: yaml
```
:::

To deploy with the [AWS CLI](https://aws.amazon.com/cli):
```
aws cloudformation deploy \
    --stack-name requests-cache \
    --template-file examples/cloudformation.yml
```
