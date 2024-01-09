# {fas}`info-circle` Advanced Requests
Following are some tips on using requests-cache with some of the more
[advanced features](https://requests.readthedocs.io/en/latest/user/advanced/) of the requests
library.

## Event Hooks
Requests has an [event hook](https://requests.readthedocs.io/en/latest/user/advanced/#event-hooks)
system that can be used to add custom behavior into different parts of the request process.
It can be used, for example, for request throttling:

:::{dropdown} Example
:animate: fade-in-slide-down
:color: primary
:icon: file-code

```python
>>> import time
>>> import requests
>>> from requests_cache import CachedSession

>>> def make_throttle_hook(timeout=1.0):
>>>     """Make a request hook function that adds a custom delay for non-cached requests"""
>>>     def hook(response, *args, **kwargs):
>>>         if not getattr(response, 'from_cache', False):
>>>             print('sleeping')
>>>             time.sleep(timeout)
>>>         return response
>>>     return hook

>>> session = CachedSession()
>>> session.hooks['response'].append(make_throttle_hook(0.1))
>>> # The first (real) request will have an added delay
>>> session.get('https://httpbin.org/get')
>>> session.get('https://httpbin.org/get')
```
:::

## Streaming Requests
If you use [streaming requests](https://requests.readthedocs.io/en/latest/user/advanced/#id9), you
can use the same code to iterate over both cached and non-cached requests. Cached response content
will have already been read (i.e., consumed), but will be available for re-reading so it behaves like
the original streamed response:

:::{dropdown} Example
:animate: fade-in-slide-down
:color: primary
:icon: file-code

```python
>>> from requests_cache import CachedSession

>>> session = CachedSession()
>>> for i in range(2):
...     response = session.get('https://httpbin.org/stream/20', stream=True)
...     for chunk in response.iter_lines():
...         print(chunk.decode('utf-8'))
```
:::
