Changelog
---------

0.1.3 (2012-05-04)
+++++++++++++++++++

* Thread safety for default ``sqlite`` backend
* Take into account the POST parameters when cache is configured
  with 'POST' in ``allowable_methods``


0.1.2 (2012-05-02)
+++++++++++++++++++

* Reduce number of ``sqlite`` database write operations
* ``fast_save`` option for ``sqlite`` backend


0.1.1 (2012-04-11)
+++++++++++++++++++

* Fix: restore responses from response.history
* Internal refactoring (``MemoryCache`` -> ``BaseCache``, ``reduce_response``
  and ``restore_response`` moved to ``BaseCache``)
* ``connection`` option for ``MongoCache``


0.1.0 (2012-04-10)
+++++++++++++++++++

* initial PyPI release