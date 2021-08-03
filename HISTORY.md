# History

### 0.7.3 (2021-08-TBD)
* SQLite backend: Update `DbCache.clear()` to succeed even if the database is corrupted
* SQLite backend: update `DbDict.bulk_delete()` to split the operation into multiple statements to support
  deleting more items than SQLite's variable limit (999)
* Filesystem backend: When using JSON serializer, pretty-print JSON by default
* Filesystem backend: Add an appropriate file extension to cache files (`.json`, `.yaml`, `.pkl`, etc.) by default.
  Can be overridden or disabled with the `extension` parameter.
* Add a `BaseCache.delete_urls()` method to bulk delete multiple responses from the cache based on request URL

### 0.7.2 (2021-07-21)
* Add support for `Response.next` (to get the next request in a redirect chain) when 302 responses are cached directly
* Add a `CachedResponse.cache_key` attribute
* Make `CachedResponse` a non-slotted class to allow client code to set arbitrary attributes on it

### 0.7.1 (2021-07-09)
* Fix a bug in which Cache-Control headers would be used unexpectedly

## 0.7.0 (2021-07-07)
[See all issues and PRs for 0.7](https://github.com/reclosedev/requests-cache/milestone/2?closed=1)

### Backends
* Add a filesystem backend that stores responses as local files
* SQLite and filesystem: Add `use_temp` option to store files in a temp directory
* SQLite: Use persistent thread-local connections, and improve performance for bulk operations
* DynamoDB: Fix `DynamoDbDict.__iter__` to return keys instead of values
* MongoDB: Remove usage of deprecated pymongo `Collection.find_and_modify()`
* Allow passing any backend-specific connection kwargs via `CachedSession` to the underlying connection function or object:
    * SQLite: `sqlite3.connect`
    * DynamoDB: `boto3.resource`
    * Redis: `redis.Redis`
    * MongoDB and GridFS: `pymongo.MongoClient`

### Expiration
* Add optional support for the following **request** headers:
    * `Cache-Control: max-age`
    * `Cache-Control: no-cache`
    * `Cache-Control: no-store`
* Add optional support for the following **response** headers:
    * `Cache-Control: max-age`
    * `Cache-Control: no-store`
    * `Expires`
* Add `cache_control` option to `CachedSession` to enable usage of cache headers
* Add support for HTTP timestamps (RFC 5322) in ``expire_after`` parameters
* Add support for bypassing the cache if `expire_after=0`
* Add support for making a cache whitelist using URL patterns

### Serialization
* Add data models for all serialized objects
* Add a BSON serializer
* Add a JSON serializer
* Add optional support for `cattrs`
* Add optional support for `ultrajson`

### General
* Add option to manually cache response objects with `BaseCache.save_response()`
* Add `BaseCache.keys()` and `values()` methods
* Add `BaseCache.response_count()` method to get an accurate count of responses (excluding invalid and expired)
* Show summarized response details with `str(CachedResponse)`
* Add more detailed repr methods for `CachedSession`, `CachedResponse`, and `BaseCache`
* Add support for caching multipart form uploads
* Update `BaseCache.urls` to only skip invalid responses, not delete them (for better performance)
* Update `old_data_on_error` option to also handle error response codes
* Update `ignored_parameters` to also exclude ignored request params, body params, or headers from cached response data (to avoid storing API keys or other credentials)
* Only log request exceptions if `old_data_on_error` is set

### Compatibility, packaging, and tests
* Fix some compatibility issues with `requests 2.17` and `2.18`
* Add minimum `requests` version of `2.17`
* Run tests for each supported version of `requests`
* Add some package extras to install optional dependencies (via `pip install`):
    * `requests-cache[bson]`
    * `requests-cache[json]`
    * `requests-cache[dynamodb]`
    * `requests-cache[mongodb]`
    * `requests-cache[redis]`
* Packaging is now handled with Poetry. For users, installation still works the same. For developers,
  see [Contributing Guide](https://requests-cache.readthedocs.io/en/stable/contributing.html) for details
* requests-cache is now fully typed and PEP-561 compliant

-----
### 0.6.4 (2021-06-04)
Fix a bug in which `filter_fn()` would get called on `response.request` instead of `response`

### 0.6.3 (2021-04-21)
* Fix false positive warning with `include_get_headers`
* Fix handling of `decode_content` parameter for `CachedResponse.raw.read()`
* Replace deprecated pymongo `Collection.count()` with `estimated_document_count()`

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
[See all issues and PRs for 0.6](https://github.com/reclosedev/requests-cache/milestone/1?closed=1)

Thanks to [Code Shelter](https://www.codeshelter.co) and
[contributors](https://requests-cache.readthedocs.io/en/stable/contributors.html)
for making this release possible!

### Backends
* SQLite: Allow passing user paths (`~/path-to-cache`) to database file with `db_path` param
* SQLite: Add `timeout` parameter
* Make default table names consistent across backends (`'http_cache'`)

### Expiration
* Cached responses are now stored with an absolute expiration time, so `CachedSession.expire_after`
  no longer applies retroactively. To revalidate previously cached items with a new expiration time,
  see below:
* Add support for overriding original expiration (i.e., revalidating) in `CachedSession.remove_expired_responses()`
* Add support for setting expiration for individual requests
* Add support for setting expiration based on URL glob patterns
* Add support for setting expiration as a `datetime`
* Add support for explicitly disabling expiration with `-1` (Since `None` may be ambiguous in some cases)

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
  for [compatibility with other requests-based libraries](https://requests-cache.readthedocs.io/en/stable/advanced_usage.html#library-compatibility).
* Add `HEAD` to default `allowable_methods`

### Docs & Tests
* Add type annotations to main functions/methods in public API, and include in documentation on
  [readthedocs](https://requests-cache.readthedocs.io/en/stable/)
* Add [Contributing Guide](https://requests-cache.readthedocs.io/en/stable/contributing.html),
  [Security](https://requests-cache.readthedocs.io/en/stable/security.html) info,
  and more examples & detailed usage info in
  [User Guide](https://requests-cache.readthedocs.io/en/stable/user_guide.html) and
  [Advanced Usage](https://requests-cache.readthedocs.io/en/stable/advanced_usage.html) sections.
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
