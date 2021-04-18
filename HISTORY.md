# History

### 0.6.3 (2021-TBD)
* Fix false positive warning with `include_get_headers`


### 0.6.2 (2021-04-14)
* Explicitly include docs, tests, and examples in sdist

### 0.6.1 (2021-04-13)
* Handle errors due to invalid responses in `BaseCache.urls`
* Add recently renamed `BaseCache.remove_old_entries()` back, as an alias with a DeprecationWarning
* Make parent dirs for new SQLite databases
* Add `aws_access_key_id` and `aws_secret_access_key` kwargs to `DynamoDbDict`
* Update `GridFSPickleDict.__delitem__` to raise a KeyError for missing items
* Demote most `logging.info` statements to debug level
* Exclude test directory from `find_packages()`
* Make integration tests easier to run and/or fail more quickly in environments where Docker isn't available

## 0.6.0 (2021-04-09)
[See all included issues and PRs](https://github.com/reclosedev/requests-cache/milestone/1?closed=1)

Thanks to [Code Shelter](https://www.codeshelter.co) and
[contributors](https://requests-cache.readthedocs.io/en/latest/contributors.html)
for making this release possible!

### Serialization
**Note:** Due to the following changes, responses cached with previous versions of requests-cache
will be invalid. These **old responses will be treated as expired**, and will be refreshed the
next time they are requested. They can also be manually converted or removed, if needed (see notes below).

* Add [example script](https://github.com/reclosedev/requests-cache/blob/master/examples/convert_cache.py)
  to convert an existing cache from previous serialization format to new one
* When running `remove_expired_responses()`, also remove responses that are invalid due to updated
  serialization format 
* Add `CachedResponse` class to wrap cached `requests.Response` objects, which makes additional
  cache information available to client code
* Add `CachedHTTPResponse` class to wrap `urllib3.response.HTTPResponse` objects, available via `CachedResponse.raw`
  * Re-construct the raw response on demand to avoid storing extra data in the cache
  * Improve emulation of raw request behavior used for iteration, streaming requests, etc.
* Add `BaseCache.urls` property to get all URLs persisted in the cache
* Add optional support for `itsdangerous` for more secure serialization

### Cache Expiration
* Cached responses are now stored with an absolute expiration time, so `CachedSession.expire_after`
  no longer applies retroactively. To revalidate previously cached items with a new expiration time,
  see below:
* Add support for overriding original expiration (i.e., revalidating) in `CachedSession.remove_expired_responses()`
* Add support for setting expiration for individual requests
* Add support for setting expiration based on URL glob patterns
* Add support for setting expiration as a `datetime`
* Add support for explicitly disabling expiration with `-1` (Since `None` may be ambiguous in some cases)

### Backends
* SQLite: Allow passing user paths (`~/path-to-cache`) to database file with `db_path` param
* SQLite: Add `timeout` parameter
* Make default table names consistent across backends (`'http_cache'`)

### Bugfixes
* Fix caching requests with data specified in `json` parameter
* Fix caching requests with `verify` parameter
* Fix duplicate cached responses due to some unhandled variations in URL format
  * To support this, the `url-normalize` library has been added to dependencies
* Fix usage of backend-specific params when used in place of `cache_name`
* Fix potential TypeError with `DbPickleDict` initialization
* Fix usage of `CachedSession.cache_disabled` if used within another contextmanager
* Fix non-thread-safe iteration in `BaseCache`
* Fix `get_cache()`, `clear()`, and `remove_expired_responses()` so they will do nothing if
  requests-cache is not installed
* Update usage of deprecated MongoClient `save()` method
* Replace some old bugs with new and different bugs, just to keep life interesting

### General
* Drop support for python <= 3.5
* Add `CacheMixin` class to make the features of `CachedSession` usable as a mixin class,
  for [compatibility with other requests-based libraries](https://requests-cache.readthedocs.io/en/latest/advanced_usage.html#library-compatibility).
* Add `HEAD` to default `allowable_methods`

### Docs & Tests
* Add type annotations to main functions/methods in public API, and include in documentation on
  [readthedocs](https://requests-cache.readthedocs.io/en/latest/)
* Add [Contributing Guide](https://requests-cache.readthedocs.io/en/latest/contributing.html),
  [Security](https://requests-cache.readthedocs.io/en/latest/security.html) info,
  and more examples & detailed usage info in
  [User Guide](https://requests-cache.readthedocs.io/en/latest/user_guide.html) and
  [Advanced Usage](https://requests-cache.readthedocs.io/en/latest/advanced_usage.html) sections.
* Increase test coverage and rewrite most tests using pytest
* Add containerized backends for both local and CI integration testing

-----
### 0.5.2 (2019-08-14)
* Fix DeprecationWarning from collections #140

### 0.5.1 (2019-08-13)
* Remove Python 2.6 Testing from travis #133
* Fix DeprecationWarning from collections #131
* vacuum the sqlite database after clearing a table #134
* Fix handling of unpickle errors #128

## 0.5.0 (2019-04-18)
Project is now added to [Code Shelter](https://www.codeshelter.co)

* Add gridfs support, thanks to @chengguangnan
* Add dynamodb support, thanks to @ar90n
* Add response filter #104, thanks to @christopher-dG
* Fix bulk_commit #78
* Fix remove_expired_responses missed in __init__.py #93
* Fix deprecation warnings #122, thanks to mbarkhau

-----
### 0.4.13 (2016-12-23)
* Support PyMongo3, thanks to @craigls #72
* Fix streaming releate issue #68

### 0.4.12 (2016-03-19)
* Fix ability to pass backend instance in `install_cache` #61

### 0.4.11 (2016-03-07)
* `ignore_parameters` feature, thanks to @themiurgo and @YetAnotherNerd (#52, #55)
* More informative message for missing backend dependencies, thanks to @Garrett-R (#60)

### 0.4.10 (2015-04-28)
* Better transactional handling in sqlite #50, thanks to @rgant
* Compatibility with streaming in requests >= 2.6.x

### 0.4.9 (2015-01-17)
* `expire_after` now also accepts `timedelta`, thanks to @femtotrader
* Added Ability to include headers to cache key (`include_get_headers` option)
* Added string representation for `CachedSession`

### 0.4.8 (2014-12-13)
* Fix bug in reading cached streaming response

### 0.4.7 (2014-12-06)
* Fix compatibility with Requests > 2.4.1 (json arg, response history)

### 0.4.6 (2014-10-13)
* Monkey patch now uses class instead lambda (compatibility with rauth)
* Normalize (sort) parameters passed as builtin dict

### 0.4.5 (2014-08-22)
* Requests==2.3.0 compatibility, thanks to @gwillem

### 0.4.4 (2013-10-31)
* Check for backend availability in install_cache(), not at the first request
* Default storage fallbacks to memory if `sqlite` is not available

### 0.4.3 (2013-09-12)
* Fix `response.from_cache` not set in hooks

### 0.4.2 (2013-08-25)
* Fix `UnpickleableError` for gzip responses

### 0.4.1 (2013-08-19)
* `requests_cache.enabled()` context manager
* Compatibility with Requests 1.2.3 cookies handling

## 0.4.0 (2013-04-25)
* Redis backend. Thanks to @michaelbeaumont
* Fix for changes in Requests 1.2.0 hooks dispatching

-----
## 0.3.0 (2013-02-24)
* Support for `Requests` 1.x.x
* `CachedSession`
* Many backward incompatible changes

-----
### 0.2.1 (2013-01-13)
* Fix broken PyPi package

## 0.2.0 (2013-01-12)
* Last backward compatible version for `Requests` 0.14.2

-----
### 0.1.3 (2012-05-04)
* Thread safety for default `sqlite` backend
* Take into account the POST parameters when cache is configured
  with 'POST' in `allowable_methods`

### 0.1.2 (2012-05-02)
* Reduce number of `sqlite` database write operations
* `fast_save` option for `sqlite` backend

### 0.1.1 (2012-04-11)
* Fix: restore responses from response.history
* Internal refactoring (`MemoryCache` -> `BaseCache`, `reduce_response`
  and `restore_response` moved to `BaseCache`)
* `connection` option for `MongoCache`

## 0.1.0 (2012-04-10)
* initial PyPI release
