API
===
This section covers all the public interfaces of ``requests-cache``

Public API
----------
.. Explicitly show inherited method docs on CachedSession instead of CachedMixin
.. autoclass:: requests_cache.core.CachedSession
    :members: send, request, cache_disabled, remove_expired_responses
    :show-inheritance:

.. autoclass:: requests_cache.core.CacheMixin

.. automodule:: requests_cache.core
    :members:
    :exclude-members: CachedSession, CacheMixin

.. automodule:: requests_cache.response
    :members:

----------------------------------------------

Cache Backends
--------------
.. automodule:: requests_cache.backends.base
   :members:

.. _cache-backends:

.. automodule:: requests_cache.backends.sqlite
   :members:

.. automodule:: requests_cache.backends.mongo
   :members:

.. automodule:: requests_cache.backends.gridfs
   :members:

.. automodule:: requests_cache.backends.redis
   :members:

.. automodule:: requests_cache.backends.dynamodb
   :members:
