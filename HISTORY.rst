.. :changelog:

History
-------

0.4.11 (2016-03-07)
+++++++++++++++++++
* ``ignore_parameters`` feature, thanks to @themiurgo and @YetAnotherNerd (#52, #55)
* More informative message for missing backend dependencies, thanks to @Garrett-R (#60)


0.4.10 (2015-04-28)
+++++++++++++++++++
* Better transactional handling in sqlite #50, thanks to @rgant
* Compatibility with streaming in requests >= 2.6.x


0.4.9 (2015-01-17)
++++++++++++++++++

* ``expire_after`` now also accepts ``timedelta``, thanks to @femtotrader
* Added Ability to include headers to cache key (``include_get_headers`` option)
* Added string representation for ``CachedSession``


0.4.8 (2014-12-13)
++++++++++++++++++

* Fix bug in reading cached streaming response


0.4.7 (2014-12-06)
++++++++++++++++++

* Fix compatibility with Requests > 2.4.1 (json arg, response history)


0.4.6 (2014-10-13)
++++++++++++++++++

* Monkey patch now uses class instead lambda (compatibility with rauth)
* Normalize (sort) parameters passed as builtin dict


0.4.5 (2014-08-22)
++++++++++++++++++

* Requests==2.3.0 compatibility, thanks to @gwillem


0.4.4 (2013-10-31)
++++++++++++++++++

* Check for backend availability in install_cache(), not at the first request
* Default storage fallbacks to memory if ``sqlite`` is not available


0.4.3 (2013-09-12)
++++++++++++++++++

* Fix ``response.from_cache`` not set in hooks



0.4.2 (2013-08-25)
++++++++++++++++++

* Fix ``UnpickleableError`` for gzip responses



0.4.1 (2013-08-19)
++++++++++++++++++

* ``requests_cache.enabled()`` context manager
* Compatibility with Requests 1.2.3 cookies handling


0.4.0 (2013-04-25)
++++++++++++++++++

* Redis backend. Thanks to @michaelbeaumont
* Fix for changes in Requests 1.2.0 hooks dispatching


0.3.0 (2013-02-24)
++++++++++++++++++

* Support for ``Requests`` 1.x.x
* ``CachedSession``
* Many backward incompatible changes

0.2.1 (2013-01-13)
++++++++++++++++++

* Fix broken PyPi package

0.2.0 (2013-01-12)
++++++++++++++++++

* Last backward compatible version for ``Requests`` 0.14.2


0.1.3 (2012-05-04)
++++++++++++++++++

* Thread safety for default ``sqlite`` backend
* Take into account the POST parameters when cache is configured
  with 'POST' in ``allowable_methods``


0.1.2 (2012-05-02)
++++++++++++++++++

* Reduce number of ``sqlite`` database write operations
* ``fast_save`` option for ``sqlite`` backend


0.1.1 (2012-04-11)
++++++++++++++++++

* Fix: restore responses from response.history
* Internal refactoring (``MemoryCache`` -> ``BaseCache``, ``reduce_response``
  and ``restore_response`` moved to ``BaseCache``)
* ``connection`` option for ``MongoCache``


0.1.0 (2012-04-10)
++++++++++++++++++

* initial PyPI release
