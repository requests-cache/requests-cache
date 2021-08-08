(advanced-usage)=
# Advanced Usage
This section covers some more advanced and use-case-specific features.

## Cache Inspection
Here are some ways to get additional information out of the cache session, backend, and responses:

### Response Details
The following attributes are available on responses:
- `from_cache`: indicates if the response came from the cache
- `created_at`: {py:class}`~datetime.datetime` of when the cached response was created or last updated
- `expires`: {py:class}`~datetime.datetime` after which the cached response will expire
- `is_expired`: indicates if the cached response is expired (if an old response was returned due to a request error)

Examples:
:::{admonition} Example code
:class: toggle
```python
>>> from requests_cache import CachedSession
>>> session = CachedSession(expire_after=timedelta(days=1))

>>> # Placeholders are added for non-cached responses
>>> response = session.get('http://httpbin.org/get')
>>> print(response.from_cache, response.created_at, response.expires, response.is_expired)
False None None None

>>> # Values will be populated for cached responses
>>> response = session.get('http://httpbin.org/get')
>>> print(response.from_cache, response.created_at, response.expires, response.is_expired)
True 2021-01-01 18:00:00 2021-01-02 18:00:00 False

>>> # Print a response object to get general information about it
>>> print(response)
'request: GET https://httpbin.org/get, response: 200 (308 bytes), created: 2021-01-01 22:45:00 IST, expires: 2021-01-02 18:45:00 IST (fresh)'
```
:::

### Cache Contents
You can use `CachedSession.cache.urls` to see all URLs currently in the cache:
```python
>>> session = CachedSession()
>>> print(session.cache.urls)
['https://httpbin.org/get', 'https://httpbin.org/stream/100']
```

If needed, you can get more details on cached responses via `CachedSession.cache.responses`, which
is a dict-like interface to the cache backend. See {py:class}`.CachedResponse` for a full list of
attributes available.

For example, if you wanted to to see all URLs requested with a specific method:
```python
>>> post_urls = [
...     response.url for response in session.cache.responses.values()
...     if response.request.method == 'POST'
... ]
```

You can also inspect `CachedSession.cache.redirects`, which maps redirect URLs to keys of the
responses they redirect to.

Additional `keys()` and `values()` wrapper methods are available on {py:class}`.BaseCache` to get
combined keys and responses.
```python
>>> print('All responses:')
>>> for response in session.cache.values():
>>>     print(response)

>>> print('All cache keys for redirects and responses combined:')
>>> print(list(session.cache.keys()))
```

Both methods also take a `check_expiry` argument to exclude expired responses:
```python
>>> print('All unexpired responses:')
>>> for response in session.cache.values(check_expiry=True):
>>>     print(response)
```

Similarly, you can get a count of responses with {py:meth}`.BaseCache.response_count`, and optionally
exclude expired responses:
```python
>>> print(f'Total responses: {session.cache.response_count()}')
>>> print(f'Unexpired responses: {session.cache.response_count(check_expiry=True)}')
```

## Custom Response Filtering
If you need more advanced behavior for determining what to cache, you can provide a custom filtering
function via the `filter_fn` param. This can by any function that takes a {py:class}`requests.Response`
object and returns a boolean indicating whether or not that response should be cached. It will be applied
to both new responses (on write) and previously cached responses (on read):

:::{admonition} Example code
:class: toggle
```python
>>> from sys import getsizeof
>>> from requests_cache import CachedSession

>>> def filter_by_size(response):
>>>     """Don't cache responses with a body over 1 MB"""
>>>     return getsizeof(response.content) <= 1024 * 1024

>>> session = CachedSession(filter_fn=filter_by_size)
```
:::

## Custom Backends
If the built-in {py:mod}`Cache Backends <requests_cache.backends>` don't suit your needs, you can
create your own by making subclasses of {py:class}`.BaseCache` and {py:class}`.BaseStorage`:

:::{admonition} Example code
:class: toggle
```python
>>> from requests_cache import CachedSession
>>> from requests_cache.backends import BaseCache, BaseStorage

>>> class CustomCache(BaseCache):
...     """Wrapper for higher-level cache operations. In most cases, the only thing you need
...     to specify here is which storage class(es) to use.
...     """
...     def __init__(self, **kwargs):
...         super().__init__(**kwargs)
...         self.redirects = CustomStorage(**kwargs)
...         self.responses = CustomStorage(**kwargs)

>>> class CustomStorage(BaseStorage):
...     """Dict-like interface for lower-level backend storage operations"""
...     def __init__(self, **kwargs):
...         super().__init__(**kwargs)
...
...     def __getitem__(self, key):
...         pass
...
...     def __setitem__(self, key, value):
...         pass
...
...     def __delitem__(self, key):
...         pass
...
...     def __iter__(self):
...         pass
...
...     def __len__(self):
...         pass
...
...     def clear(self):
...         pass
```
:::

You can then use your custom backend in a {py:class}`.CachedSession` with the `backend` parameter:
```python
>>> session = CachedSession(backend=CustomCache())
```

## Custom Serializers
If the built-in {ref}`serializers` don't suit your needs, you can create your own. For example, if
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
:::{admonition} Example code
:class: toggle
```python
>>> import pickle, gzip
>>> from requests_cache.serialzers import SerializerPipeline, Stage
>>> compressed_serializer = SerializerPipeline([
...     pickle,
...     Stage(gzip, dumps='compress', loads='decompress'),
...])
>>> session = CachedSession(serializer=compressed_serializer)
```
:::

### Text-based Serializers
If you're using a text-based serialization format like JSON or YAML, some extra steps are needed to
encode binary data and non-builtin types. The [cattrs](https://cattrs.readthedocs.io) library can do
the majority of the work here, and some pre-configured converters are included for serveral common
formats in the {py:mod}`.preconf` module.

For example, a compressed JSON pipeline could be built as follows:
:::{admonition} Example code
:class: toggle
```python
>>> import json, gzip, codecs
>>> from requests_cache.serializers import SerializerPipeline, Stage, json_converter
>>> comp_json_serializer = SerializerPipeline([
...     json_converter, # Serialize to a JSON string
...     Stage(codecs.utf_8, dumps='encode', loads='decode'), # Encode to bytes
...     Stage(gzip, dumps='compress', loads='decompress'), # Compress
...])
```
:::

```{note}
If you want to use a different format that isn't included in {py:mod}`.preconf`, you can use
{py:class}`.CattrStage` as a starting point.
```

```{note}
If you want to convert a string representation to bytes (e.g. for compression), you must use a codec
from {py:mod}`.codecs` (typically `codecs.utf_8`)
```

### Additional Serialization Steps
Some other tools that could be used as a stage in a {py:class}`.SerializerPipeline` include:

class                                             | loads     | dumps
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
## Usage with other requests features

### Request Hooks
Requests has an [Event Hook](https://requests.readthedocs.io/en/master/user/advanced/#event-hooks)
system that can be used to add custom behavior into different parts of the request process.
It can be used, for example, for request throttling:

:::{admonition} Example code
:class: toggle
```python
>>> import time
>>> import requests
>>> from requests_cache import CachedSession
>>>
>>> def make_throttle_hook(timeout=1.0):
>>>     """Make a request hook function that adds a custom delay for non-cached requests"""
>>>     def hook(response, *args, **kwargs):
>>>         if not getattr(response, 'from_cache', False):
>>>             print('sleeping')
>>>             time.sleep(timeout)
>>>         return response
>>>     return hook
>>>
>>> session = CachedSession()
>>> session.hooks['response'].append(make_throttle_hook(0.1))
>>> # The first (real) request will have an added delay
>>> session.get('http://httpbin.org/get')
>>> session.get('http://httpbin.org/get')
```
:::

### Streaming Requests
:::{note}
This feature requires `requests >= 2.19`
:::

If you use [streaming requests](https://2.python-requests.org/en/master/user/advanced/#id9), you
can use the same code to iterate over both cached and non-cached requests. A cached request will,
of course, have already been read, but will use a file-like object containing the content:

:::{admonition} Example code
:class: toggle
```python
>>> from requests_cache import CachedSession
>>>
>>> session = CachedSession()
>>> for i in range(2):
...     response = session.get('https://httpbin.org/stream/20', stream=True)
...     for chunk in response.iter_lines():
...         print(chunk.decode('utf-8'))
```
:::

(library-compatibility)=
## Usage with other requests-based libraries
This library works by patching and/or extending {py:class}`requests.Session`. Many other libraries out there
do the same thing, making it potentially difficult to combine them.

For that scenario, a mixin class is provided, so you can create a custom class with behavior from multiple
Session-modifying libraries:
```python
>>> from requests import Session
>>> from requests_cache import CacheMixin
>>> from some_other_lib import SomeOtherMixin
>>>
>>> class CustomSession(CacheMixin, SomeOtherMixin, Session):
...     """Session class with features from both some_other_lib and requests-cache"""
```

### Requests-HTML
[requests-html](https://github.com/psf/requests-html) is one library that works with this method:
:::{admonition} Example code
:class: toggle
```python
>>> import requests
>>> from requests_cache import CacheMixin, install_cache
>>> from requests_html import HTMLSession
>>>
>>> class CachedHTMLSession(CacheMixin, HTMLSession):
...     """Session with features from both CachedSession and HTMLSession"""
>>>
>>> session = CachedHTMLSession()
>>> response = session.get('https://github.com/')
>>> print(response.from_cache, response.html.links)
```
:::


Or if you are using {py:func}`.install_cache`, you can use the `session_factory` argument:
:::{admonition} Example code
:class: toggle
```python
>>> install_cache(session_factory=CachedHTMLSession)
>>> response = requests.get('https://github.com/')
>>> print(response.from_cache, response.html.links)
```
:::

The same approach can be used with other libraries that subclass {py:class}`requests.Session`.

### Requests-futures
Some libraries, including [requests-futures](https://github.com/ross/requests-futures),
support wrapping an existing session object:
```python
>>> session = FutureSession(session=CachedSession())
```

In this case, `FutureSession` must wrap `CachedSession` rather than the other way around, since
`FutureSession` returns (as you might expect) futures rather than response objects.
See [issue #135](https://github.com/reclosedev/requests-cache/issues/135) for more notes on this.

### Internet Archive
Usage with [internetarchive](https://github.com/jjjake/internetarchive) is the same as other libraries
that subclass `requests.Session`:
:::{admonition} Example code
:class: toggle
```python
>>> from requests_cache import CacheMixin
>>> from internetarchive.session import ArchiveSession
>>>
>>> class CachedArchiveSession(CacheMixin, ArchiveSession):
...     """Session with features from both CachedSession and ArchiveSession"""
```
:::

### Requests-mock
[requests-mock](https://github.com/jamielennox/requests-mock) has multiple methods for mocking
requests, including a contextmanager, decorator, fixture, and adapter. There are a few different
options for using it with requests-cache, depending on how you want your tests to work.

#### Disabling requests-cache
If you have an application that uses requests-cache and you just want to use requests-mock in
your tests, the easiest thing to do is to disable requests-cache.

For example, if you are using {py:func}`.install_cache` in your application and the
requests-mock [pytest fixture](https://requests-mock.readthedocs.io/en/latest/pytest.html) in your
tests, you could wrap it in another fixture that uses {py:func}`.uninstall_cache` or {py:func}`.disabled`:
:::{admonition} Example code
:class: toggle
```{literalinclude} ../tests/compat/test_requests_mock_disable_cache.py
```
:::

Or if you use a `CachedSession` object, you could replace it with a regular `Session`, for example:
:::{admonition} Example code
:class: toggle
```python
import unittest
import pytest
import requests

@pytest.fixure(scope='function', autouse=True)
def disable_requests_cache():
    """Replace CachedSession with a regular Session for all test functions"""
    with unittest.mock.patch('requests_cache.CachedSession', requests.Session):
        yield
```
:::

#### Combining requests-cache with requests-mock
If you want both caching and mocking features at the same time, you can attach requests-mock's
[adapter](https://requests-mock.readthedocs.io/en/latest/adapter.html) to a `CachedSession`:

:::{admonition} Example code
:class: toggle
```{literalinclude} ../tests/compat/test_requests_mock_combine_cache.py
```
:::

#### Building a mocker using requests-cache data
Another approach is to use cached data to dynamically define mock requests + responses.
This has the advantage of only using request-mock's behavior for
[request matching](https://requests-mock.readthedocs.io/en/latest/matching.html).

:::{admonition} Example code
:class: toggle
```{literalinclude} ../tests/compat/test_requests_mock_load_cache.py
:lines: 21-40
```
:::

To turn that into a complete example:
:::{admonition} Example code
:class: toggle
```{literalinclude} ../tests/compat/test_requests_mock_load_cache.py
```
:::

### Responses
Usage with the [responses](https://github.com/getsentry/responses) library is similar to the
requests-mock examples above.

:::{admonition} Example code
:class: toggle
```{literalinclude} ../tests/compat/test_responses_load_cache.py
```
:::