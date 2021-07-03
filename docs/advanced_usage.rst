.. _advanced_usage:

Advanced Usage
==============
This section covers some more advanced and use-case-specific features.

.. contents::
    :local:

Cache Inspection
----------------
Here are some ways to get additional information out of the cache session, backend, and responses:

Response Details
~~~~~~~~~~~~~~~~
The following attributes are available on responses:

* ``from_cache``: indicates if the response came from the cache
* ``created_at``: :py:class:`~datetime.datetime` of when the cached response was created or last updated
* ``expires``: :py:class:`~datetime.datetime` after which the cached response will expire
* ``is_expired``: indicates if the cached response is expired (if an old response was returned due to a request error)

Examples:

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

Alternatively, you can just print a response object to get general information about it:

    >>> print(response)
    'request: GET https://httpbin.org/get, response: 200 (308 bytes), created: 2021-01-01 22:45:00 IST, expires: 2021-01-02 18:45:00 IST (fresh)'

Cache Contents
~~~~~~~~~~~~~~
You can use ``CachedSession.cache.urls`` to see all URLs currently in the cache:

    >>> session = CachedSession()
    >>> print(session.cache.urls)
    ['https://httpbin.org/get', 'https://httpbin.org/stream/100']

If needed, you can get more details on cached responses via ``CachedSession.cache.responses``, which
is a dict-like interface to the cache backend. See :py:class:`.CachedResponse` for a full list of
attributes available.

For example, if you wanted to to see all URLs requested with a specific method:

    >>> post_urls = [
    >>>     response.url for response in session.cache.responses.values()
    >>>     if response.request.method == 'POST'
    >>> ]

You can also inspect ``CachedSession.cache.redirects``, which maps redirect URLs to keys of the
responses they redirect to.

Additional ``keys()`` and ``values()`` wrapper methods are available on :py:class:`.BaseCache` to get
combined keys and responses.

    >>> print('All responses:')
    >>> for response in session.cache.values():
    >>>     print(response)

    >>> print('All cache keys for redirects and responses combined:')
    >>> print(list(session.cache.keys()))

Both methods also take a ``check_expiry`` argument to exclude expired responses:

    >>> print('All unexpired responses:')
    >>> for response in session.cache.values(check_expiry=True):
    >>>     print(response)

Similarly, you can get a count of responses with :py:meth:`.BaseCache.response_count`, and optionally
exclude expired responses:

    >>> print(f'Total responses: {session.cache.response_count()}')
    >>> print(f'Unexpired responses: {session.cache.response_count(check_expiry=True)}')

Custom Response Filtering
-------------------------
If you need more advanced behavior for determining what to cache, you can provide a custom filtering
function via the ``filter_fn`` param. This can by any function that takes a :py:class:`requests.Response`
object and returns a boolean indicating whether or not that response should be cached. It will be applied
to both new responses (on write) and previously cached responses (on read). Example:

    >>> from sys import getsizeof
    >>> from requests_cache import CachedSession
    >>>
    >>> def filter_by_size(response):
    >>>     """Don't cache responses with a body over 1 MB"""
    >>>     return getsizeof(response.content) <= 1024 * 1024
    >>>
    >>> session = CachedSession(filter_fn=filter_by_size)

Custom Backends
---------------
If the built-in :py:mod:`Cache Backends <requests_cache.backends>` don't suit your needs, you can
create your own by making subclasses of :py:class:`.BaseCache` and :py:class:`.BaseStorage`.

Example:

    >>> from requests_cache import CachedSession
    >>> from requests_cache.backends import BaseCache, BaseStorage
    >>>
    >>> class CustomCache(BaseCache):
    ...     """Wrapper for higher-level cache operations. In most cases, the only thing you need
    ...     to specify here is which storage class(es) to use.
    ...     """
    ...     def __init__(self, **kwargs):
    ...         super().__init__(**kwargs)
    ...         self.redirects = CustomStorage(**kwargs)
    ...         self.responses = CustomStorage(**kwargs)
    >>>
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

You can then use your custom backend in a :py:class:`.CachedSession` with the ``backend`` parameter:

    >>> session = CachedSession(backend=CustomCache())

Custom Serializers
------------------
If the built-in :ref:`serializers` don't suit your needs, you can use any object with dumps/loads methods that takes
python classes as input, and returns either :py:class:.`str` or :py:class:`.bytes` objects.

Example using an imaginary ``custom_pickle`` module that provides ``dumps`` and ``loads`` functions:

    >>> import custom_pickle
    >>> from requests_cache import CachedSession
    >>>
    >>> session = CachedSession(serializer=custom_pickle)

More complex serialization can be done with :py:class:`.SerializerPipeline`. Applications include text-based serialization
(e.g. json / bson / msgpack / yaml / toml), signing, compression, and/or encryption. Any combination of these can be built using
a multi-stage serializer composed with :py:class:`.SerializerPipeline`. A valid :py:class:`.SerializerPipeline` is any pipeline
that starts with python objects, and ends with a :py:class:.`str` or :py:class:`.bytes` object. A valid stage of a pipeline is
any object with a dumps/loads method. If the object has similar methods (e.g. compress / decompress), those can be aliased
using :py:class:.`.Stage`.

For example, a compressed pickle serializer can be built as:

    >>> import pickle, gzip
    >>> from requests_cache.serialzers import SerializerPipeline, Stage
    >>> compressed_serializer = SerializerPipeline([pickle, Stage(gzip, dumps='compress', loads='decompress')])
    >>> session = CachedSession(serializer=compressed_serializer)

If you want to build a :py:class:`.SerializerPipeline` that works with a string version of cached requests, then the native
python objects must first be converted to a dict-of-dicts format. Requeses_cache comes with support for this out of the box
with cattr converters for most common text formats at `requests_cache.serializers.preconf`. For example, a compressed json
pipeline could be built as follows:

    >>> import json, gzip, codecs
    >>> from requests_cache.serializers import SerializerPipeline, Stage
    >>> from requests_cache.serializers.preconf import json_converter
    >>> comp_json_serializer = SerializerPipeline([
    ...     json_converter, # Convert Python objects to dict-of-dicts
    ...     json, # Convert to string
    ...     Stage(codecs.utf_8, dumps='encode', loads='decode'), # Convert to bytes
    ...     Stage(gzip, dumps='compress', loads='decompress'), # Compress
    ]

Two gotchas to watch out for:

- If you want to work with a string representation, the first stage must come from requests_cache.serializers.preconf
- If you want to convert a string representation to bytes (e.g. for compression), you must use a codec from codecs
  (pretty much always codecs.utf_8)


Some of the other classes / objects that may be used with :py:class:`.SerializerPipelines` include:

class                              loads    dumps
=================================  =====    =====
pickle                             dumps    loads
gzip / zlib / bz2 / lzma           compress decompress
codecs.[anything]                  encode   decode
itsdangerous.Signer                sign     unsign
itsdangerous.serializer.Serializer dumps    loads
cryptography.fernet.Fernet         encrypt  decrypt


Usage with other requests features
----------------------------------

Request Hooks
~~~~~~~~~~~~~
Requests has an `Event Hook <https://requests.readthedocs.io/en/master/user/advanced/#event-hooks>`_
system that can be used to add custom behavior into different parts of the request process.
It can be used, for example, for request throttling:

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

Streaming Requests
~~~~~~~~~~~~~~~~~~
.. note::
    This feature requires ``requests >= 2.19``

If you use `streaming requests <https://2.python-requests.org/en/master/user/advanced/#id9>`_, you
can use the same code to iterate over both cached and non-cached requests. A cached request will,
of course, have already been read, but will use a file-like object containing the content.
Example:

    >>> from requests_cache import CachedSession
    >>>
    >>> session = CachedSession()
    >>> for i in range(2):
    ...     response = session.get('https://httpbin.org/stream/20', stream=True)
    ...     for chunk in response.iter_lines():
    ...         print(chunk.decode('utf-8'))


.. _library_compatibility:

Usage with other requests-based libraries
-----------------------------------------
This library works by patching and/or extending :py:class:`requests.Session`. Many other libraries out there
do the same thing, making it potentially difficult to combine them. For that scenario, a mixin class
is provided, so you can create a custom class with behavior from multiple Session-modifying libraries:

    >>> from requests import Session
    >>> from requests_cache import CacheMixin
    >>> from some_other_lib import SomeOtherMixin
    >>>
    >>> class CustomSession(CacheMixin, SomeOtherMixin, Session):
    ...     """Session class with features from both requests-html and requests-cache"""

Requests-HTML
~~~~~~~~~~~~~
Example with `requests-html <https://github.com/psf/requests-html>`_:

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

Or, using the monkey-patch method:

    >>> install_cache(session_factory=CachedHTMLSession)
    >>> response = requests.get('https://github.com/')
    >>> print(response.from_cache, response.html.links)

The same approach can be used with other libraries that subclass :py:class:`requests.Session`.

Requests-futures
~~~~~~~~~~~~~~~~
Example with `requests-futures <https://github.com/ross/requests-futures>`_:

Some libraries, including ``requests-futures``, support wrapping an existing session object:

    >>> session = FutureSession(session=CachedSession())

In this case, ``FutureSession`` must wrap ``CachedSession`` rather than the other way around, since
``FutureSession`` returns (as you might expect) futures rather than response objects.
See `issue #135 <https://github.com/reclosedev/requests-cache/issues/135>`_ for more notes on this.

Requests-mock
~~~~~~~~~~~~~
Example with `requests-mock <https://github.com/jamielennox/requests-mock>`_:

Requests-mock works a bit differently. It has multiple methods of mocking requests, and the
method most compatible with requests-cache is attaching its
`adapter <https://requests-mock.readthedocs.io/en/latest/adapter.html>`_ to a CachedSession:

    >>> import requests
    >>> from requests_mock import Adapter
    >>> from requests_cache import CachedSession
    >>>
    >>> # Set up a CachedSession that will make mock requests where it would normally make real requests
    >>> adapter = Adapter()
    >>> adapter.register_uri(
    ...     'GET',
    ...     'mock://some_test_url',
    ...     headers={'Content-Type': 'text/plain'},
    ...     text='mock response',
    ...     status_code=200,
    ... )
    >>> session = CachedSession()
    >>> session.mount('mock://', adapter)
    >>>
    >>> session.get('mock://some_test_url', text='mock_response')
    >>> response = session.get('mock://some_test_url')
    >>> print(response.text)

Internet Archive
~~~~~~~~~~~~~~~~
Example with `internetarchive <https://github.com/jjjake/internetarchive>`_:

Usage is the same as other libraries that subclass `requests.Session`:

    >>> from requests_cache import CacheMixin
    >>> from internetarchive.session import ArchiveSession
    >>>
    >>> class CachedArchiveSession(CacheMixin, ArchiveSession):
    ...     """Session with features from both CachedSession and ArchiveSession"""
