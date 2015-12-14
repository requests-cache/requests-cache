.. _user_guide:

User guide
==========


Installation
------------

Install with pip_ or easy_install_::

    pip install --upgrade requests-cache

or download latest version from version control::

    git clone git://github.com/reclosedev/requests-cache.git
    cd requests-cache
    python setup.py install


.. warning:: Version updates of ``requests``, ``urllib3`` or ``requests_cache`` itself can break existing
            cache database (see https://github.com/reclosedev/requests-cache/issues/56 ).
            So if your code relies on cache, or is expensive in terms of time and traffic, please be sure to use
            something like ``virtualenv`` and pin your requirements.

.. _pip: http://pypi.python.org/pypi/pip/
.. _easy_install: http://pypi.python.org/pypi/setuptools

Usage
-----

.. currentmodule:: requests_cache.core

There is two ways of using :mod:`requests_cache`:

 - Using :class:`CachedSession` instead ``requests.Session``
 - Monkey patching ``requests`` to use :class:`CachedSession` by default

Monkey-patching allows to add caching to existent program by adding just two lines:

Import :mod:`requests_cache` and call :func:`install_cache`
::

    import requests
    import requests_cache

    requests_cache.install_cache()

And you can use ``requests``, all responses will be cached transparently!

For example, following code will take only 1-2 seconds instead 10::

    for i in range(10):
        requests.get('http://httpbin.org/delay/1')

Cache can be configured with some options, such as cache filename, backend
(sqlite, mongodb, redis, memory), expiration time, etc. E.g. cache stored in sqlite
database (default format) named ``'test_cache.sqlite'`` with expiration
set to 300 seconds can be configured as::

    requests_cache.install_cache('test_cache', backend='sqlite', expire_after=300)

.. seealso::
    Full list of options can be found in
    :func:`requests_cache.install_cache() <requests_cache.core.install_cache>` reference


Transparent caching is achieved by monkey-patching ``requests`` library
It is possible to uninstall this patch with :func:`requests_cache.uninstall_cache() <requests_cache.core.uninstall_cache>`.

Also, you can use :func:`requests_cache.disabled() <requests_cache.core.disabled>`
context manager for temporary disabling caching::

    with requests_cache.disabled():
        print(requests.get('http://httpbin.org/ip').text)


If ``Response`` is taken from cache, ``from_cache`` attribute will be ``True``:
::

    >>> import requests
    >>> import requests_cache
    >>> requests_cache.install_cache()
    >>> requests_cache.clear()
    >>> r = requests.get('http://httpbin.org/get')
    >>> r.from_cache
    False
    >>> r = requests.get('http://httpbin.org/get')
    >>> r.from_cache
    True

It can be used, for example, for request throttling with help of ``requests`` hook system::

        import time
        import requests
        import requests_cache

        def make_throttle_hook(timeout=1.0):
            """
            Returns a response hook function which sleeps for `timeout` seconds if
            response is not cached
            """
            def hook(response):
                if not getattr(response, 'from_cache', False):
                    print 'sleeping'
                    time.sleep(timeout)
                return response
            return hook

        if __name__ == '__main__':
            requests_cache.install_cache('wait_test')
            requests_cache.clear()

            s = requests_cache.CachedSession()
            s.hooks = {'response': make_throttle_hook(0.1)}
            s.get('http://httpbin.org/delay/get')
            s.get('http://httpbin.org/delay/get')

.. seealso:: `example.py <https://github.com/reclosedev/requests-cache/blob/master/example.py>`_

.. note:: requests_cache prefetchs response content, be aware if your code uses streaming requests.

.. _persistence:

Persistence
-----------

:mod:`requests_cache` designed to support different backends for persistent storage.
By default it uses ``sqlite`` database. Type of storage can be selected with ``backend`` argument of :func:`install_cache`.

List of available backends:

- ``'sqlite'``  - sqlite database (**default**)
- ``'memory'``  - not persistent,  stores all data in Python ``dict`` in memory
- ``'mongodb'`` - (**experimental**) MongoDB database (``pymongo < 3.0`` required)
- ``'redis'``   - stores all data on a redis data store (``redis`` required)

You can write your own and pass instance to :func:`install_cache` or :class:`CachedSession` constructor.
See :ref:`cache_backends` API documentation and sources.

.. _expiration:

Expiration
----------

If you are using cache with ``expire_after`` parameter set, responses are removed from the storage only when the same
request is made. Since the store sizes can get out of control pretty quickly with expired items
you can remove them using :func:`remove_expired_responses`
or :meth:`BaseCache.remove_old_entries(created_before) <requests_cache.backends.base.BaseCache.remove_old_entries>`.
::

    expire_after = timedelta(hours=1)
    requests_cache.install_cache(expire_after=expire_after)
    ...
    requests_cache.remove_expired_responses()
    # or
    remove_old_entries.get_cache().remove_old_entries(datetime.utcnow() - expire_after)
    # when used as session
    session = CachedSession(..., expire_after=expire_after)
    ...
    session.cache.remove_old_entries(datetime.utcnow() - expire_after)


For more information see :doc:`API reference <api>`.
