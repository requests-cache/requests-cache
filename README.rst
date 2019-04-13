requests-cache
---------------

Requests-cache is a transparent persistent cache for requests_ (version >= 1.1.0) library.

.. _requests: http://python-requests.org/

.. image:: https://travis-ci.org/reclosedev/requests-cache.svg?branch=master
    :target: https://travis-ci.org/reclosedev/requests-cache

.. image:: https://coveralls.io/repos/reclosedev/requests-cache/badge.svg?branch=master&service=github
    :target: https://coveralls.io/github/reclosedev/requests-cache?branch=master

.. image:: https://www.codeshelter.co/static/badges/badge-flat.svg
    :target: https://www.codeshelter.co/
    :alt: Code Shelter


Usage example
-------------

Just write:

.. code-block:: python

    import requests
    import requests_cache
    
    requests_cache.install_cache('demo_cache')

And all responses with headers and cookies will be transparently cached to
`demo_cache.sqlite` database. For example, following code will take only
1-2 seconds instead of 10, and will run instantly on next launch:

.. code-block:: python

    for i in range(10):
        requests.get('http://httpbin.org/delay/1')
    
It can be useful when you are creating some simple data scraper with constantly
changing parsing logic or data format, and don't want to redownload pages or
write complex error handling and persistence.

Note
----

``requests-cache`` ignores all cache headers, it just caches the data for the
time you specify.

If you need library which knows how to use HTTP headers and status codes,
take a look at `httpcache <https://github.com/Lukasa/httpcache>`_ and
`CacheControl <https://github.com/ionrock/cachecontrol>`_.

Links
-----

- **Documentation** at `readthedocs.org <https://requests-cache.readthedocs.io/>`_

- **Source code and issue tracking** at `GitHub <https://github.com/reclosedev/requests-cache>`_.

- **Working example** at `Real Python <https://realpython.com/blog/python/caching-external-api-requests>`_.
