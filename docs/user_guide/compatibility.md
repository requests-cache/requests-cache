<!-- TODO: Fix relative links -->
(compatibility)=
# {fa}`plus-square` Usage with other requests-based libraries
This library works by patching and/or extending {py:class}`requests.Session`. Many other libraries
out there do the same thing, making it potentially difficult to combine them.

For that scenario, a mixin class is provided, so you can create a custom class with behavior from
multiple Session-modifying libraries:
```python
>>> from requests import Session
>>> from requests_cache import CacheMixin
>>> from some_other_lib import SomeOtherMixin

>>> class CustomSession(CacheMixin, SomeOtherMixin, Session):
...     """Session class with features from both some_other_lib and requests-cache"""
```

## Requests-HTML
[requests-html](https://github.com/psf/requests-html) is one library that works with this method:
```python
>>> import requests
>>> from requests_cache import CacheMixin, install_cache
>>> from requests_html import HTMLSession

>>> class CachedHTMLSession(CacheMixin, HTMLSession):
...     """Session with features from both CachedSession and HTMLSession"""

>>> session = CachedHTMLSession()
>>> response = session.get('https://github.com/')
>>> print(response.from_cache, response.html.links)
```


Or if you are using {py:func}`.install_cache`, you can use the `session_factory` argument:
```python
>>> install_cache(session_factory=CachedHTMLSession)
>>> response = requests.get('https://github.com/')
>>> print(response.from_cache, response.html.links)
```

The same approach can be used with other libraries that subclass {py:class}`requests.Session`.

## Requests-Futures
Some libraries, including [requests-futures](https://github.com/ross/requests-futures),
support wrapping an existing session object:
```python
>>> from requests_cache import CachedSession
>>> from requests_futures.sessions import FuturesSession

>>> session = FutureSession(session=CachedSession())
```

In this case, `FutureSession` must wrap `CachedSession` rather than the other way around, since
`FutureSession` returns (as you might expect) futures rather than response objects.
See [issue #135](https://github.com/reclosedev/requests-cache/issues/135) for more notes on this.

## Requests-OAuthlib
Usage with [requests-oauthlib](https://github.com/requests/requests-oauthlib) is the same as other
libraries that subclass `requests.Session`:
```python
>>> from requests_cache import CacheMixin
>>> from requests_oauthlib import OAuth2Session

>>> class CachedOAuth2Session(CacheMixin, OAuth2Session):
...     """Session with features from both CachedSession and OAuth2Session"""

>>> session = CachedOAuth2Session('my_client_id')
```

## Requests-Ratelimiter
[requests-ratelimiter](https://github.com/JWCook/requests-ratelimiter) adds rate-limiting to
requests via the [pyrate-limiter](https://github.com/vutran1710/PyrateLimiter) library. It also
provides a mixin, but note that the inheritance order is important: If rate-limiting is applied
_after_ caching, you get the added benefit of not counting cache hits against your rate limit.
```python
>>> from pyrate_limiter import RedisBucket, RequestRate, Duration
>>> from requests import Session
>>> from requests_cache import CacheMixin, RedisCache
>>> from requests_ratelimiter import LimiterMixin

>>> class CachedLimiterSession(CacheMixin, LimiterMixin, Session):
...     """Session class with caching and rate-limiting behavior. Accepts arguments for both
...     LimiterSession and CachedSession.
...     """

>>> # Limit non-cached requests to 5 requests per second, with unlimited cached requests
>>> # Optionally use Redis as both the bucket backend and the cache backend
>>> session = CachedLimiterSession(
...     rates=RequestRate(5, Duration.SECOND),
...     bucket_class=RedisBucket,
...     backend=RedisCache(),
... )
```

## Internet Archive
Usage with [internetarchive](https://github.com/jjjake/internetarchive) is the same as other libraries
that subclass `requests.Session`:
```python
>>> from requests_cache import CacheMixin
>>> from internetarchive.session import ArchiveSession

>>> class CachedArchiveSession(CacheMixin, ArchiveSession):
...     """Session with features from both CachedSession and ArchiveSession"""

>>> session = CachedArchiveSession()
```

## Requests-Mock
[requests-mock](https://github.com/jamielennox/requests-mock) has multiple methods for mocking
requests, including a contextmanager, decorator, fixture, and adapter. There are a few different
options for using it with requests-cache, depending on how you want your tests to work.

### Disabling requests-cache
If you have an application that uses requests-cache and you just want to use requests-mock in
your tests, the easiest thing to do is to disable requests-cache.

For example, if you are using {py:func}`.install_cache` in your application and the
requests-mock [pytest fixture](https://requests-mock.readthedocs.io/en/latest/pytest.html) in your
tests, you could wrap it in another fixture that uses {py:func}`.uninstall_cache` or
{py:func}`.disabled`:
:::{admonition} Example: test_requests_mock_disable_cache.py
:class: toggle
```{literalinclude} ../../tests/compat/test_requests_mock_disable_cache.py
```
:::


Or if you use a `CachedSession` object, you could replace it with a regular `Session`, for example:
```python
>>> import unittest
>>> import pytest
>>> import requests

>>> @pytest.fixure(scope='function', autouse=True)
>>> def disable_requests_cache():
...     """Replace CachedSession with a regular Session for all test functions"""
...     with unittest.mock.patch('requests_cache.CachedSession', requests.Session):
...         yield
```

### Combining requests-cache with requests-mock
If you want both caching and mocking features at the same time, you can attach requests-mock's
[adapter](https://requests-mock.readthedocs.io/en/latest/adapter.html) to a `CachedSession`:

:::{admonition} Example: test_requests_mock_combine_cache.py
:class: toggle
```{literalinclude} ../../tests/compat/test_requests_mock_combine_cache.py
```
:::

### Building a mocker using requests-cache data
Another approach is to use cached data to dynamically define mock requests + responses.
This has the advantage of only using request-mock's behavior for
[request matching](https://requests-mock.readthedocs.io/en/latest/matching.html).

```{literalinclude} ../../tests/compat/test_requests_mock_load_cache.py
:lines: 21-40
```

To turn that into a complete example:
:::{admonition} Example: test_requests_mock_load_cache.py
:class: toggle
```{literalinclude} ../../tests/compat/test_requests_mock_load_cache.py
```
:::

## Responses
Usage with the [responses](https://github.com/getsentry/responses) library is similar to the
requests-mock examples above.

:::{admonition} Example: test_responses_load_cache.py
:class: toggle
```{literalinclude} ../../tests/compat/test_responses_load_cache.py
```
:::
