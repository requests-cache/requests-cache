(serializers)=
# {fas}`barcode` Serializers
![](../_static/file-pickle_32px.png)
![](../_static/file-json_32px.png)
![](../_static/file-yaml_32px.png)
![](../_static/file-toml_32px.png)

Some alternative serializers are included, mainly intended for use with {py:class}`.FileCache`.

:::{note}
Some of these serializers require additional dependencies, listed in the sections below.
:::

## Specifying a Serializer
Similar to {ref}`backends`, you can specify which serializer to use with the `serializer` parameter
for either {py:class}`.CachedSession` or {py:func}`.install_cache`.

## Built-in Serializers

### JSON Serializer
Storing responses as JSON gives you the benefit of making them human-readable and editable, in
exchange for a minor reduction in read and write speeds.

Usage:
```python
>>> session = CachedSession('my_cache', serializer='json')
```

:::{dropdown} Example JSON-serialized Response (with decoded JSON content)
:animate: fade-in-slide-down
:color: primary
:icon: file-code

```{literalinclude} ../sample_data/sample_response_json.json
:language: JSON
```
:::
:::{dropdown} Example JSON-serialized Response (with binary content)
:animate: fade-in-slide-down
:color: primary
:icon: file-code

```{literalinclude} ../sample_data/sample_response_binary.json
:language: JSON
```
:::

This will use [ultrajson](https://github.com/ultrajson/ultrajson) if installed, otherwise the stdlib
`json` module will be used. You can install the optional dependencies for this serializer with:
```bash
pip install requests-cache[json]
```

### YAML Serializer
YAML is another option if you need a human-readable/editable format, with the same tradeoffs as JSON.

Usage:
```python
>>> session = CachedSession('my_cache', serializer='yaml')
```

:::{dropdown} Example YAML-serialized Response (with decoded JSON content)
:animate: fade-in-slide-down
:color: primary
:icon: file-code

```{literalinclude} ../sample_data/sample_response_json.yaml
:language: YAML
```
:::
:::{dropdown} Example YAML-serialized Response (with binary content)
:animate: fade-in-slide-down
:color: primary
:icon: file-code

```{literalinclude} ../sample_data/sample_response_binary.yaml
:language: YAML
```
:::

You can install the extra dependencies for this serializer with:
```bash
pip install requests-cache[yaml]
```

### BSON Serializer
[BSON](https://www.mongodb.com/json-and-bson) is a serialization format originally created for
MongoDB, but it can also be used independently. Compared to JSON, it has better performance
(although still not as fast as `pickle`), and adds support for additional data types. It is not
human-readable, but some tools support reading and editing it directly.

Usage:
```python
>>> session = CachedSession('my_cache', serializer='bson')
```

You can install the extra dependencies for this serializer with:
```bash
pip install requests-cache[mongo]
```

Or if you would like to use the standalone BSON codec for a different backend, without installing
MongoDB dependencies:
```bash
pip install requests-cache[bson]
```

## Response Content Format
By default, any JSON or text response body will be decoded, so the response is fully
human-readable/editable. Other content types will be saved as binary data. To save _all_ content as binary, set ``decode_content=False``:
```python
>>> backend = FileCache(decode_content=False)
>>> session = CachedSession('http_cache', backend=backend)
```

## Serializer Security
See {ref}`security` for recommended setup steps for more secure cache serialization, particularly
when using {py:mod}`pickle`.

(custom-serializers)=
## Custom Serializers
If the built-in serializers don't suit your needs, you can create your own. For example, if
you had a imaginary `custom_pickle` module that provides `dumps` and `loads` functions:
```python
>>> import custom_pickle
>>> from requests_cache import CachedSession
>>> session = CachedSession(serializer=custom_pickle)
```

### Serializer Pipelines
More complex serialization can be done with {py:class}`.SerializerPipeline`. Use cases include
text-based serialization, compression, encryption, and any other intermediate steps you might want
to add.

Any combination of these can be composed with a {py:class}`.SerializerPipeline`, which starts with a
{py:class}`.CachedResponse` and ends with a {py:class}`.str` or {py:class}`.bytes` object. Each stage
of the pipeline can be any object or module with `dumps` and `loads` functions. If the object has
similar methods with different names (e.g. `compress` / `decompress`), those can be aliased using
{py:class}`.Stage`.

For example, a compressed pickle serializer can be built as:
:::{dropdown} Example
:animate: fade-in-slide-down
:color: primary
:icon: file-code

```python
>>> import gzip
>>> from requests_cache import CachedSession, SerializerPipeline, Stage, pickle_serializer
>>> compressed_serializer = SerializerPipeline(
...     [
...         pickle_serializer,
...         Stage(dumps=gzip.compress, loads=gzip.decompress),
...     ],
...     is_binary=True,
... )
>>> session = CachedSession(serializer=compressed_serializer)
```
:::

### Text-based Serializers
If you're using a text-based serialization format like JSON or YAML, some extra steps are needed to
encode binary data and non-builtin types. The [cattrs](https://cattrs.readthedocs.io) library can do
the majority of the work here, and some pre-configured converters are included for several common
formats in the {py:mod}`.preconf` module.

For example, a compressed JSON pipeline could be built as follows:
:::{dropdown} Example
:animate: fade-in-slide-down
:color: primary
:icon: file-code

```python
>>> import json, gzip
>>> from requests_cache import CachedSession, SerializerPipeline, Stage, json_serializer, utf8_encoder
>>> comp_json_serializer = SerializerPipeline([
...     json_serializer, # Serialize to a JSON string
...     utf8_encoder, # Encode to bytes
...     Stage(dumps=gzip.compress, loads=gzip.decompress), # Compress
... ])
```
:::

```{note}
If you want to use a different format that isn't included in {py:mod}`.preconf`, you can use
{py:class}`.CattrStage` as a starting point.
```

### Additional Serialization Steps
Some other tools that could be used as a stage in a {py:class}`.SerializerPipeline` include:

Class                                             | loads     | dumps
-----                                             | -----     | -----
{py:mod}`codecs.* <.codecs>`                      | encode    | decode
{py:mod}`.bz2`                                    | compress  | decompress
{py:mod}`.gzip`                                   | compress  | decompress
{py:mod}`.lzma`                                   | compress  | decompress
{py:mod}`.zlib`                                   | compress  | decompress
{py:mod}`.pickle`                                 | dumps     | loads
{py:class}`itsdangerous.signer.Signer`            | sign      | unsign
{py:class}`itsdangerous.serializer.Serializer`    | loads     | dumps
{py:class}`cryptography.fernet.Fernet`            | encrypt   | decrypt
