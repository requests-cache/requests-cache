API
===

This part of the documentation covers all the interfaces of `requests-cache`


Public api
----------

.. automodule:: requests_cache.core
   :members:


----------------------------------------------

.. _cache_backends:

Cache backends
--------------

.. automodule:: requests_cache.backends.base
   :members:

.. _backends_sqlite:

.. automodule:: requests_cache.backends.sqlite
   :members:

.. _backends_mongo:

.. automodule:: requests_cache.backends.mongo
   :members:

.. _backends_redis:

.. automodule:: requests_cache.backends.redis
   :members:

----------------------------------------------

Internal modules which can be used outside
------------------------------------------

.. _backends_dbdict:

.. automodule:: requests_cache.backends.storage.dbdict
   :members:

.. automodule:: requests_cache.backends.storage.mongodict
   :members:

.. automodule:: requests_cache.backends.storage.redisdict
   :members:
