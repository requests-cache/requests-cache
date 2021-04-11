User Guide
==========
This section covers the main features of requests-cache.

.. contents::
    :local:
    :depth: 2

Installation
------------
Install with pip:

    $ pip install requests-cache

Requirements
~~~~~~~~~~~~
* Requires python 3.6+.
* You may need additional dependencies depending on which backend you want to use. To install with
  extra dependencies for all supported :ref:`user_guide:cache backends`:

    $ pip install requests-cache[backends]

Optional Setup Steps
~~~~~~~~~~~~~~~~~~~~
* See :ref:`security` for recommended setup steps for more secure cache serialization.
* See :ref:`Contributing Guide <contributing:dev installation>` for setup steps for local development.

General Usage
-------------
There are two main ways of using requests-cache:

* **Sessions:** (recommended) Use :py:class:`.CachedSession` to send your requests
* **Patching:** Globally patch ``requests`` using :py:func:`.install_cache()`

Sessions
~~~~~~~~
:py:class:`.CachedSession` can be used as a drop-in replacement for :py:class:`requests.Session`.
Basic usage looks like this:

    >>> from requests_cache import CachedSession
    >>>
    >>> session = CachedSession()
    >>> session.get('http://httpbin.org/get')

Any :py:class:`requests.Session` method can be used (but see :ref:`user_guide:http methods` section
below for config details):

    >>> session.request('GET', 'http://httpbin.org/get')
    >>> session.head('http://httpbin.org/get')

Caching can be temporarily disabled with :py:meth:`.CachedSession.cache_disabled`:

    >>> with session.cache_disabled():
    ...     session.get('http://httpbin.org/get')

The best way to clean up your cache is through :ref:`user_guide:cache expiration`, but you can also
clear out everything at once with :py:meth:`.BaseCache.clear`:

    >>> session.cache.clear()

Patching
~~~~~~~~
In some situations, it may not be possible or convenient to manage your own session object. In those
cases, you can use :py:func:`.install_cache` to add caching to all ``requests`` functions:

    >>> import requests
    >>> import requests_cache
    >>>
    >>> requests_cache.install_cache()
    >>> requests.get('http://httpbin.org/get')

As well as session methods:

    >>> session = requests.Session()
    >>> session.get('http://httpbin.org/get')

:py:func:`.install_cache` accepts all the same parameters as :py:class:`.CachedSession`:

    >>> requests_cache.install_cache(expire_after=360, allowable_methods=('GET', 'POST'))

It can be temporarily :py:func:`.enabled`:

    >>> with requests_cache.enabled():
    ...     requests.get('http://httpbin.org/get')  # Will be cached

Or temporarily :py:func:`.disabled`:

    >>> requests_cache.install_cache()
    >>> with requests_cache.disabled():
    ...     requests.get('http://httpbin.org/get')  # Will not be cached

Or completely removed with :py:func:`.uninstall_cache`:

    >>> requests_cache.uninstall_cache()
    >>> requests.get('http://httpbin.org/get')

You can also clear out all responses in the cache with :py:func:`.clear`, and check if
requests-cache is currently installed with :py:func:`.is_installed`.

Limitations
^^^^^^^^^^^
Like any other utility that uses global patching, there are some scenarios where you won't want to
use :py:func:`.install_cache`:

* In a multi-threaded or multiprocess application
* In an application that uses other packages that extend or modify :py:class:`requests.Session`
* In a package that will be used by other packages or applications

Cache Backends
--------------
Several cache backends are included, which can be selected with
the ``backend`` parameter for either :py:class:`.CachedSession` or :py:func:`.install_cache`:

* ``'sqlite'``: `SQLite <https://www.sqlite.org>`_ database (**default**)
* ``'redis'``: `Redis <https://redis.io>`_ cache (requires ``redis``)
* ``'mongodb'``: `MongoDB <https://www.mongodb.com>`_ database (requires ``pymongo``)
* ``'gridfs'``: `GridFS <https://docs.mongodb.com/manual/core/gridfs/>`_ collections on a MongoDB database (requires ``pymongo``)
* ``'dynamodb'``: `Amazon DynamoDB <https://aws.amazon.com/dynamodb>`_ database (requires ``boto3``)
* ``'memory'`` : A non-persistent cache that just stores responses in memory

A backend can be specified either by name, class or instance:

    >>> from requests_cache.backends import RedisCache
    >>> from requests_cache import CachedSession
    >>>
    >>> # Backend name
    >>> session = CachedSession(backend='redis', namespace='my-cache')

    >>> # Backend class
    >>> session = CachedSession(backend=RedisCache, namespace='my-cache')

    >>> # Backend instance
    >>> session = CachedSession(backend=RedisCache(namespace='my-cache'))

See :py:mod:`requests_cache.backends` for more backend-specific usage details, and see
:ref:`advanced_usage:custom backends` for details on creating your own implementation.

Cache Name
~~~~~~~~~~
The ``cache_name`` parameter will be used as follows depending on the backend:

* ``sqlite``: Database path, e.g ``~/.cache/my_cache.sqlite``
* ``dynamodb``: Table name
* ``mongodb`` and ``gridfs``: Database name
* ``redis``: Namespace, meaning all keys will be prefixed with ``'<cache_name>:'``

Cache Options
-------------
A number of options are available to modify which responses are cached and how they are cached.

HTTP Methods
~~~~~~~~~~~~
By default, only GET and HEAD requests are cached. To cache additional HTTP methods, specify them
with ``allowable_methods``. For example, caching POST requests can be used to ensure you don't send
the same data multiple times:

    >>> session = CachedSession(allowable_methods=('GET', 'POST'))
    >>> session.post('http://httpbin.org/post', json={'param': 'value'})

Status Codes
~~~~~~~~~~~~
By default, only responses with a 200 status code are cached. To cache additional status codes,
specify them with ``allowable_codes``"

    >>> session = CachedSession(allowable_codes=(200, 418))
    >>> session.get('http://httpbin.org/teapot')

Request Parameters
~~~~~~~~~~~~~~~~~~
By default, all request parameters are taken into account when caching responses. In some cases,
there may be request parameters that don't affect the response data, for example authentication tokens
or credentials. If you want to ignore specific parameters, specify them with ``ignored_parameters``:

    >>> session = CachedSession(ignored_parameters=['auth-token'])
    >>> # Only the first request will be sent
    >>> session.get('http://httpbin.org/get', params={'auth-token': '2F63E5DF4F44'})
    >>> session.get('http://httpbin.org/get', params={'auth-token': 'D9FAEB3449D3'})

Request Headers
~~~~~~~~~~~~~~~
By default, request headers are not taken into account when caching responses. In some cases,
different headers may result in different response data, so you may want to cache them separately.
To enable this, use ``include_get_headers``:

    >>> session = CachedSession(include_get_headers=True)
    >>> # Both of these requests will be sent and cached separately
    >>> session.get('http://httpbin.org/headers', {'Accept': 'text/plain'})
    >>> session.get('http://httpbin.org/headers', {'Accept': 'application/json'})

Cache Expiration
----------------
By default, cached responses will be stored indefinitely. You can initialize the cache with an
``expire_after`` value to specify how long responses will be cached.

Expiration Types
~~~~~~~~~~~~~~~~
``expire_after`` can be any of the following:

* ``-1`` (to never expire)
* A positive number (in seconds)
* A :py:class:`~datetime.timedelta`
* A :py:class:`~datetime.datetime`

Examples:

    >>> # Set expiration for the session using a value in seconds
    >>> session = CachedSession(expire_after=360)

    >>> # To specify a different unit of time, use a timedelta
    >>> from datetime import timedelta
    >>> session = CachedSession(expire_after=timedelta(days=30))

    >>> # Update an existing session to disable expiration (i.e., store indefinitely)
    >>> session.expire_after = -1

Expiration Scopes
~~~~~~~~~~~~~~~~~
Passing ``expire_after`` to :py:class:`.CachedSession` will set the expiration for the duration of that session.
Expiration can also be set on a per-URL or per-request basis. The following order of precedence
is used:

1. Per-request expiration (``expire_after`` argument for :py:meth:`.CachedSession.request`)
2. Per-URL expiration (``urls_expire_after`` argument for :py:class:`.CachedSession`)
3. Per-session expiration (``expire_after`` argument for :py:class:`.CachedSession`)

To set expiration for a single request:

    >>> session.get('http://httpbin.org/get', expire_after=360)

URL Patterns
~~~~~~~~~~~~
You can use ``urls_expire_after`` to set different expiration values for different requests, based on
URL glob patterns. This allows you to customize caching based on what you know about the resources
you're requesting. For example, you might request one resource that gets updated frequently, another
that changes infrequently, and another that never changes. Example:

    >>> urls_expire_after = {
    ...     '*.site_1.com': 30,
    ...     'site_2.com/resource_1': 60 * 2,
    ...     'site_2.com/resource_2': 60 * 60 * 24,
    ...     'site_2.com/static': -1,
    ... }
    >>> session = CachedSession(urls_expire_after=urls_expire_after)

**Notes:**

* ``urls_expire_after`` should be a dict in the format ``{'pattern': expire_after}``
* ``expire_after`` accepts the same types as ``CachedSession.expire_after``
* Patterns will match request **base URLs**, so the pattern ``site.com/resource/`` is equivalent to
  ``http*://site.com/resource/**``
* If there is more than one match, the first match will be used in the order they are defined
* If no patterns match a request, ``CachedSession.expire_after`` will be used as a default.

Removing Expired Responses
~~~~~~~~~~~~~~~~~~~~~~~~~~
For better performance, expired responses won't be removed immediately, but will be removed
(or replaced) the next time they are requested. To manually clear all expired responses, use
:py:meth:`.CachedSession.remove_expired_responses`:

    >>> session.remove_expired_responses()

Or, when using patching:

    >>> requests_cache.remove_expired_responses()

You can also apply a different ``expire_after`` to previously cached responses, which will
revalidate the cache with the new expiration time:

    >>> session.remove_expired_responses(expire_after=timedelta(days=30))

Potential Issues
----------------
* Version updates of ``requests``, ``urllib3`` or ``requests-cache`` itself may not be compatible with
  previously cached data (see issues `#56 <https://github.com/reclosedev/requests-cache/issues/56>`_
  and `#102 <https://github.com/reclosedev/requests-cache/issues/102>`_).
  The best way to prevent this is to use a virtualenv and pin your dependency versions.
* See :ref:`security` for notes on serialization security
