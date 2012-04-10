.. _user_guide:

User guide
==========


Installation
------------

Install with pip_ or easy_install_::

    pip install --upgrade requests-cache

or download latest version from version control::

    hg clone https://bitbucket.org/reclosedev/requests-cache
    cd requests-cache
    python setup.py install

.. _pip: http://pypi.python.org/pypi/pip/
.. _easy_install: http://pypi.python.org/pypi/setuptools

Usage
-----

.. currentmodule:: requests_cache.core

Just import :mod:`requests_cache` and call :func:`configure`
::

    import requests
    import requests_cache

    request_cache.configure()

And you can use ``requests``, all responses will be cached transparently!

For example, following code will take only 1-2 seconds instead 10::

    for i in range(10):
        requests.get('http://httpbin.org/delay/1')

Cache can be configured with some options, such as cache filename, backend (sqlite, memory),
expiration time, etc. E.g. cache stored in sqlite database (default)
named ``'test_cache.sqlite'`` with expiration set to 5 minutes can be configured as::

    request_cache.configure('test_cache', backend='sqlite', expire_after=5)

.. seealso::
    Full list of options can be found in
    :func:`requests_cache.configure() <requests_cache.core.configure>` reference


Transparent caching is achieved by monkey-patching ``requests`` library
(it can be disabled, see ``monkey_patch`` argument for :func:`configure`) ,
It is possible to undo this patch, and redo it again with :func:`undo_patch` and
:func:`redo_patch`. But preferable way is to use :func:`requests_cache.disabled() <requests_cache.core.disabled>`
and :func:`requests_cache.enabled <requests_cache.core.enabled>` context managers for temporary disabling and enabling caching::

    with requests_cache.disabled():
        for i in range(3):
            print(requests.get('http://httpbin.org/ip').text)

    with requests_cache.enabled():
        for i in range(10):
            print(requests.get('http://httpbin.org/delay/1').text)

Also you can check if url is present in cache with :func:`requests_cache.has_url() <requests_cache.core.has_url>`
and delete it with :func:`requests_cache.delete_url() <requests_cache.core.delete_url>`
::

    >>> import requests
    >>> import requests_cache
    >>> request_cache.configure()
    >>> requests.get('http://httpbin.org/get')
    >>> requests_cache.has_ulr('http://httpbin.org/get')
    True
    >>> requests_cache.delete_ulr('http://httpbin.org/get')
    >>> requests_cache.has_ulr('http://httpbin.org/get')
    False

Persistence
-----------

:mod:`requests_cache` designed to support different backends for persistent storage.
By default it uses ``sqlite`` database. Type of storage can be selected with ``backend`` argument of :func:`configure`.

List of available backends:

- ``'sqlite'``  - sqlite database (**default**)
- ``'memory'``  - not persistent,  stores all data in Python ``dict`` in memory
- ``'mongodb'`` - (**experimental**) MongoDB database (``pymongo`` required)

  .. note:: ``pymongo`` doesn't work fine with `gevent <http://www.gevent.org/>`_ which powers ``requests.async``.
            But there is some workarounds, see question on
            `StackOverflow <http://stackoverflow.com/questions/7166998/pymongo-gevent-throw-me-a-banana-and-just-monkey-patch>`_.

Also, you can write your own. See :ref:`cache_backends` API documentation and sources.

----------------------

For more information see :doc:`API reference <api>` and example_.

.. _example: https://bitbucket.org/reclosedev/requests-cache/src/tip/example.py

