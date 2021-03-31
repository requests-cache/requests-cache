.. _advanced-usage:

Advanced Usage
==============
.. contents::
    :local:

CachedSession Options
---------------------
See :py:class:`requests_cache.CachedSession` for a full list of parameters.

Cache Name
~~~~~~~~~~
The ``cache_name`` parameter will be used as follows depending on the backend:

* ``sqlite``: Cache filename, e.g ``my_cache.sqlite``
* ``mongodb``: Database name
* ``redis``: Namespace, meaning all keys will be prefixed with ``'cache_name:'``

Cache Keys
~~~~~~~~~~
The cache key is a hash created from request information, and is used as an index for cached
responses. There are a couple ways you can customize what information is used to create this key:

* Use ``include_get_headers`` if you want headers to be included in the cache key. In other
  words, this will create separate cache items for responses with different headers.
* Use ``ignored_parameters`` to exclude specific request params from the cache key. This is
  useful, for example, if you request the same resource with different credentials or access
  tokens.

HTTP methods and status codes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
You can choose which request HTTP methods and response status codes you want to cache using the
parameters ``allowable_methods`` and ``allowable_codes``, respectively. By default, only GET and HEAD
requests and 200 responses are cached. Example:

    >>> from requests_cache import CachedSession
    >>>
    >>> session = CachedSession(
    >>>     allowable_methods=('GET', 'POST'),
    >>>     allowable_codes=(200, 418),
    >>> )

Custom response filter
~~~~~~~~~~~~~~~~~~~~~~
If you need more advanced behaviour for determining what to cache, you can provide a custom filtering
function via the ``filter_fn`` param. This function that takes a :py:class:`requests.Response` object
and returns a boolean indicating whether or not that response should be cached. It will be applied to
both new responses (on write) and previously cached responses (on read). Example:

    >>> from sys import getsizeof
    >>> from requests_cache import CachedSession
    >>>
    >>> def filter_by_size(response):
    >>>     """Don't cache responses with a body over 1 MB"""
    >>>     return getsizeof(response.content) <= 1024 * 1024
    >>>
    >>>    session = CachedSession(filter_fn=filter_by_size)

Cache Expiration
~~~~~~~~~~~~~~~~
Use ``expire_after`` to specify how long responses will be cached. This can be:

* A positive number (in seconds)
* ``-1`` (to never expire)
* A :py:class:`.timedelta`
* A :py:class:`datetime`

This will only apply to responses cached in the current session; to apply a different expiration
to previously cached responses, see :py:meth:`remove_expired_responses`.

Expiration can also be set on a per-URL or per request basis. The following order of precedence
is used:

1. Per-request expiration (``expire_after`` argument for :py:meth:`.request`)
2. Per-URL expiration (``urls_expire_after`` argument for ``CachedSession``)
3. Per-session expiration (``expire_after`` argument for ``CachedSession``)

URL Patterns
~~~~~~~~~~~~
You can use ``urls_expire_after`` to set different expiration times for different requests, based on
URL glob patterns. This allows you to customize caching based on what you know about the resources
you're requesting. For example, you might request one resource that gets updated frequently, another
that changes infrequently, and another that never changes. Example:

    >>> urls_expire_after = {
    >>>    '*.site_1.com': 30,
    >>>     'site_2.com/resource_1': 60 * 2,
    >>>     'site_2.com/resource_2': 60 * 60 * 24,
    >>>     'site_2.com/static': -1,
    >>> }

**Notes:**

* ``urls_expire_after`` should be a dict in the format ``{'pattern': expire_after}``
* ``expire_after`` accepts the same types as ``CachedSession.expire_after``
* Patterns will match request **base URLs**, so the pattern ``site.com/resource/`` is equivalent to
  ``http*://site.com/resource/**``
* If there is more than one match, the first match will be used in the order they are defined
* If no patterns match a request, ``expire_after`` will be used as a default.

Cache Inspection
----------------
Here are some ways to get additional information out of the cache session, backend, and responses:

Response Attributes
~~~~~~~~~~~~~~~~~~~
The following attributes are available on responses:
* ``from_cache``: indicates if the response came from the cache
* ``created_at``: ``datetime`` of when the cached response was created or last updated
* ``expires``: ``datetime`` after which the cached response will expire
* ``is_expired``: indicates if the cached response is expired (if an old response was returned due to a request error)

Examples:

    >>> from requests_cache import CachedSession
    >>> session = CachedSession(expire_after=timedelta(days=1))

    >>> # Placeholders are added for non-cached responses
    >>> r = session.get('http://httpbin.org/get')
    >>> print(r.from_cache, r.created_at, r.expires, r.is_expired)
    False None None None

    >>> # Values will be populated for cached responses
    >>> r = session.get('http://httpbin.org/get')
    >>> print(r.from_cache, r.created_at, r.expires, r.is_expired)
    True 2021-01-01 18:00:00 2021-01-02 18:00:00 False

Cache Contents
~~~~~~~~~~~~~~
You can use :py:meth:`.CachedSession.cache.urls` to see all URLs currently in the cache:

    >>> session = CachedSession()
    >>> print(session.urls)
    ['https://httpbin.org/get', 'https://httpbin.org/stream/100']

If needed, you can get more details on cached responses via ``CachedSession.cache.responses``, which
is a dict-like interface to the cache backend. See :py:class:`requests.Response` and
:py:class:`.CachedResponse` for a full list of attributes available.

For example, if you wanted to to see all URLs requested with a specific method:

    >>> post_urls = [
    >>>     response.url for response in session.cache.responses.values()
    >>>     if response.request.method == 'POST'
    >>> ]

You can also inspect ``CachedSession.cache.redirects``, which maps redirect URLs to keys of the
responses they redirect to.

Custom Backends
---------------
If the built-in :ref:`cache-backends` don't suit your needs and you want to create your own, you can create
subclasses of :py:class:`.BaseCache` and :py:class:`.BaseStorage`:

    >>> from requests_cache import CachedSession
    >>> from requests_cache.backends import BaseCache, BaseStorage
    >>>
    >>> class MyCache(BaseCache):
    >>>     """Wrapper for higher-level cache operations"""
    >>>     def __init__(self, **kwargs):
    >>>         super().__init__(**kwargs)
    >>>         self.redirects = MyStorage(**kwargs)
    >>>         self.responses = MyStorage(**kwargs)
    >>>
    >>> class MyStorage(BaseStorage):
    >>>     """Lower-level backend storage operations"""

You can then use your custom backend in a ``CachedSession`` with the ``backend`` parameter:

    >>> session = CachedSession(backend=MyCache())

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
If you use `streaming requests <https://2.python-requests.org/en/master/user/advanced/#id9>`_, you
can use the same code to iterate over both cached and non-cached requests. A cached request will,
of course, have already been read, but will use a file-like object containing the content.
Example::

    from requests_cache import CachedSession

    session = CachedSession()
    for i in range(2):
        r = session.get('https://httpbin.org/stream/20', stream=True)
        for chunk in r.iter_lines():
            print(chunk.decode('utf-8'))


.. _library_compatibility:

Usage with other requests-based libraries
-----------------------------------------
This library works by patching and/or extending ``requests.Session``. Many other libraries out there
do the same thing, making it potentially difficult to combine them. For that scenario, a mixin class
is provided, so you can create a custom class with behavior from multiple Session-modifying libraries::

    from requests import Session
    from requests_cache import CacheMixin
    from some_other_lib import SomeOtherMixin

    class CustomSession(CacheMixin, SomeOtherMixin ClientSession):
        """Session class with features from both requests-html and requests-cache"""

Requests-HTML
~~~~~~~~~~~~~
Example with `requests-html <https://github.com/psf/requests-html>`_::

    import requests
    from requests_cache import CacheMixin, install_cache
    from requests_html import HTMLSession

    class CachedHTMLSession(CacheMixin, HTMLSession):
        """Session with features from both CachedSession and HTMLSession"""

    session = CachedHTMLSession()
    r = session.get("https://github.com/")
    print(r.from_cache, r.html.links)

Or, using the monkey-patch method::

    install_cache(session_factory=CachedHTMLSession)
    r = requests.get("https://github.com/")
    print(r.from_cache, r.html.links)

The same approach can be used with other libraries that subclass ``requests.Session``.

Requests-futures
~~~~~~~~~~~~~~~~
Example with `requests-futures <https://github.com/ross/requests-futures>`_:

Some libraries, including `requests-futures`, support wrapping an existing session object.

    session = FutureSession(session=CachedSession())

In this case, ``FutureSession`` must wrap ``CachedSession`` rather than the other way around, since
``FutureSession`` returns (as you might expect) futures rather than response objects.
See `issue #135 <https://github.com/reclosedev/requests-cache/issues/135>`_ for more notes on this.

Requests-mock
~~~~~~~~~~~~~
Example with `requests-mock <https://github.com/jamielennox/requests-mock>`_:

Requests-mock works a bit differently. It has multiple methods of mocking requests, and the
method most compatible with requests-cache is attaching its
`adapter <https://requests-mock.readthedocs.io/en/latest/adapter.html>`_ to a CachedSession::

    import requests
    from requests_mock import Adapter
    from requests_cache import CachedSession

    # Set up a CachedSession that will make mock requests where it would normally make real requests
    adapter = Adapter()
    adapter.register_uri(
        'GET',
        'mock://some_test_url',
        headers={'Content-Type': 'text/plain'},
        text='mock response',
        status_code=200,
    )
    session = CachedSession()
    session.mount('mock://', adapter)

    session.get('mock://some_test_url', text='mock_response')
    response = session.get('mock://some_test_url')
    print(response.text)

Internet Archive
~~~~~~~~~~~~~~~~
Example with `internetarchive <https://github.com/jjjake/internetarchive>`_:

Usage is the same as other libraries that subclass `requests.Session`::

    from requests_cache import CacheMixin
    from internetarchive.session import ArchiveSession

    class CachedArchiveSession(CacheMixin, ArchiveSession):
        """Session with features from both CachedSession and ArchiveSession"""

Potential Issues
----------------
* Version updates of ``requests``, ``urllib3`` or ``requests-cache`` itself may not be compatible with
  previously cached data (see issues `#56 <https://github.com/reclosedev/requests-cache/issues/56>`_
  and `#102 <https://github.com/reclosedev/requests-cache/issues/102>`_).
  The best way to prevent this is to use a virtualenv and pin your dependency versions.
* See :ref:`security` for notes on serialization security
