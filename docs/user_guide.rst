.. _user_guide:

User guide
==========

Installation
------------

Just enter in console::

    pip install --upgrade requests-cache

Or::

    easy_install -U requests-cache

Usage
-----

::

    import requests
    import requests_cache

    request_cache.configure()

    for i in range(10):
        r = requests.get('http://httpbin.org/delay/5')

Cache can be configured with some options, see
:func:`requests_cache.configure() <requests_cache.core.configure>` function reference.

`requests-cache` also provides some useful functions...

