requests-cache
---------------

Requests-cache is a transparent persistent cache for requests_ (version >= 1.1.0) library.

.. _requests: http://python-requests.org/

Usage example
-------------

Just write::

    import requests
    import requests_cache
    
    requests_cache.install_cache('demo_cache')

And all responses with headers and cookies will be transparently cached to
`demo_cache.sqlite` database. For example, following code will take only
1-2 seconds instead 10, and will run instantly on next launch::

    for i in range(10):
        requests.get('http://httpbin.org/delay/1')
    
It can be useful when you are creating some simple data scraper with constantly
changing parsing logic or data format, and don't want to redownload pages or
write complex error handling and persistence.

Note
----

``requests-cache`` ignores all cache headers, it just caches the data for the
time you specify.

Links
-----

- **Documentation** at `readthedocs.org <http://readthedocs.org/docs/requests-cache/>`_

- **Source code and issue tracking** at `GitHub <https://github.com/reclosedev/requests-cache>`_.

