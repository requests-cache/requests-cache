# History

## 0.9.2 (2022-02-15)
* Fix serialization in filesystem backend with binary content that is also valid UTF-8
* Fix some regression bugs introduced in 0.9.0:
  * Add support for `params` as a positional argument to `CachedSession.request()`
  * Add support for disabling expiration for a single request with `CachedSession.request(..., expire_after=-1)`

## 0.9.1 (2022-01-15)
* Add support for python 3.10.2 and 3.9.10 (regarding resolving `ForwardRef` types during deserialization)
* Add support for key-only request parameters (regarding hashing request data for cache key creation)
* Reduce verbosity of log messages when encountering an invalid JSON request body

## 0.9.0 (2022-01-01)
[See all issues and PRs for 0.9](https://github.com/reclosedev/requests-cache/milestone/4?closed=1)

**Expiration & Headers:**
* Use `Cache-Control` **request** headers by default
* Add support for `Cache-Control: immutable`
* Add support for immediate expiration + revalidation with `Cache-Control: max-age=0` and `Expires: 0`
* Reset expiration for cached response when a `304 Not Modified` response is received

**Backends:**
* Filesystem and SQLite backends: Add better error message if parent path exists but isn't a directory
* Redis: Improve performance by using native Redis TTL for cache expiration

**Other features:**
* Support `expire_after` param for `CachedSession.send()`

**Performance:**
* Fix duplicate read operation for checking whether to read from redirects cache
* Skip unnecessary contains check if a key is in the main responses cache
* Make per-request expiration thread-safe for both `CachedSession.request()` and `CachedSession.send()`
* Some micro-optimizations for request matching

**Bugfixes:**
* Fix regression bug causing headers used for cache key to not guarantee sort order
* Handle some additional corner cases when normalizing request data
* Add support for `BaseCache` keyword arguments passed along with a backend instance
* Fix issue with cache headers not being used correctly if `cache_control=True` is used with an `expire_after` value
* Fix license metadata as shown on PyPI
* Fix `CachedResponse` serialization behavior when using stdlib `pickle` in a custom serializer

## 0.8.1 (2021-09-15)
* Redact `ingored_parameters` from `CachedResponse.url` (if used for credentials or other sensitive info)
* Fix an incorrect debug log message about skipping cache write
* Add some additional aliases for `DbDict`, etc. so fully qualified imports don't break

## 0.8.0 (2021-09-07)
[See all issues and PRs for 0.8](https://github.com/reclosedev/requests-cache/milestone/3?closed=1)

**Expiration & Headers:**
* Add support for conditional requests and cache validation using:
    * `ETag` + `If-None-Match` headers
    * `Last-Modified` + `If-Modified-Since` headers
    * `304 Not Modified` responses
* If a cached response is expired but contains a validator, a conditional request will by sent, and a new response will be cached and returned only if the remote content has not changed

**Backends:**
* Filesystem:
    * Add `FileCache.cache_dir` wrapper property
    * Add `FileCache.paths()` method
    * Add `use_cache_dir` option to use platform-specific user cache directory
    * Return `pathlib.Path` objects for all file paths
    * Use shorter hashes for file names
* SQLite:
    * Add `SQLiteCache.db_path` wrapper property
    * Add `use_memory` option and support for in-memory databases
    * Add `use_cache_dir` option to use platform-specific user cache directory
    * Return `pathlib.Path` objects for all file paths

**Serialization:**
* Use `cattrs` by default for optimized serialization

**Other features:**
* Add `BaseCache.update()` method as a shortcut for exporting to a different cache instance
* Allow `BaseCache.has_url()` and `delete_url()` to optionally take parameters for `requests.Request` instead of just a URL
* Allow `create_key()` to optionally accept parameters for `requests.Request` instead of a request object
* Allow `match_headers` to optionally accept a list of specific headers to match
* Add support for custom cache key callbacks with `key_fn` parameter
* By default use blake2 instead of sha256 for generating cache keys
* Slightly reduce size of serialized responses

**Backwards-compatible API changes:**

The following changes are meant to make certain behaviors more obvious for new users, without breaking existing usage:
* For consistency with `Cache-Control: stale-if-error`, rename `old_data_on_error` to `stale_if_error`
  * Going forward, any new options based on a standard HTTP caching feature will be named after that feature
* For clarity about matching behavior, rename `include_get_headers` to `match_headers`
  * References in the docs to cache keys and related behavior are now described as 'request matching'
* For consistency with other backends, rename SQLite backend classes: `backends.sqlite.Db*` -> `SQLiteCache`, `SQLiteDict`, `SQLitePickleDict`
* Add aliases for all previous parameter/class names for backwards-compatibility

**Dependencies:**
* Add `appdirs` as a dependency for easier cross-platform usage of user cache directories
* Update `cattrs` from optional to required dependency
* Update `itsdangerous` from required to optional (but recommended) dependency
* Require `requests` 2.22+ and `urllib3` 1.25.5+

**Deprecations & removals:**
* Drop support for python 3.6
    * **Note:** python 3.6 support in 0.7.x will continue to be maintained at least until it reaches EOL (2021-12-23)
    * Any bugfixes for 0.8 that also apply to 0.7 will be backported
* Remove deprecated `core` module
* Remove deprecated `BaseCache.remove_old_entries()` method

-----

### 0.7.5 (2021-09-15)
* Fix incorrect location of `redirects.sqlite` when using filesystem backend
* Fix issue in which `redirects.sqlite` would get included in response paths with filesystem backend
* Add aliases for forwards-compatibility with 0.8+
* Backport fixes from 0.8.1

### 0.7.4 (2021-08-16)
* Fix an issue with httpdate strings from `Expires` headers not getting converted to UTC
* Fix a packaging issue with extra files added to top-level wheel directory
* Fix some issues with parallelizing tests using pytest-xdist

### 0.7.3 (2021-08-10)
* SQLite backend:
    * Update `DbCache.clear()` to succeed even if the database is corrupted
    * Update `DbDict.bulk_delete()` to split the operation into multiple statements to support deleting more items than SQLite's variable limit (999)
* Filesystem backend:
    * When using JSON serializer, pretty-print JSON by default
    * Add an appropriate file extension to cache files (`.json`, `.yaml`, `.pkl`, etc.) by default; can be overridden or disabled with the `extension` parameter.
* Add a `BaseCache.delete_urls()` method to bulk delete multiple responses from the cache based on
  request URL

### 0.7.2 (2021-07-21)
* Add support for `Response.next` (to get the next request in a redirect chain) when 302 responses are cached directly
* Add a `CachedResponse.cache_key` attribute
* Make `CachedResponse` a non-slotted class to allow client code to set arbitrary attributes on it

### 0.7.1 (2021-07-09)
* Fix a bug in which Cache-Control headers would be used unexpectedly

## 0.7.0 (2021-07-07)
[See all issues and PRs for 0.7](https://github.com/reclosedev/requests-cache/milestone/2?closed=1)

**Backends:**
* Add a filesystem backend that stores responses as local files
* SQLite and Filesystem: Add `use_temp` option to store files in a temp directory
* SQLite: Use persistent thread-local connections, and improve performance for bulk operations
* DynamoDB: Fix `DynamoDbDict.__iter__` to return keys instead of values
* MongoDB: Remove usage of deprecated pymongo `Collection.find_and_modify()`
* Allow passing any backend-specific connection kwargs via `CachedSession` to the underlying connection function or object:
    * SQLite: `sqlite3.connect`
    * DynamoDB: `boto3.resource`
    * Redis: `redis.Redis`
    * MongoDB and GridFS: `pymongo.MongoClient`

**Expiration & Headers:**
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
* Add support for making a cache allowlist using URL patterns

**Serialization:**
* Add data models for all serialized objects
* Add a JSON serializer
* Add a YAML serializer
* Add a BSON serializer
* Add optional support for `cattrs`
* Add optional support for `ultrajson`

**Other features:**
* requests-cache is now fully typed and PEP-561 compliant
* Add option to manually cache response objects with `BaseCache.save_response()`
* Add `BaseCache.keys()` and `values()` methods
* Add `BaseCache.response_count()` method to get an accurate count of responses (excluding invalid and expired)
* Show summarized response details with `str(CachedResponse)`
* Add more detailed repr methods for `CachedSession`, `CachedResponse`, and `BaseCache`
* Add support for caching multipart form uploads
* Update `BaseCache.urls` to only skip invalid responses, not delete them (for better performance)
* Update `ignored_parameters` to also exclude ignored request params, body params, or headers from cached response data (to avoid storing API keys or other credentials)
* Update `old_data_on_error` option to also handle error response codes
* Only log request exceptions if `old_data_on_error` is set

**Depedencies:**
* Add minimum `requests` version of `2.17`
* Add `attrs` as a dependency for improved serialization models
* Add `cattrs` as an optional dependency
* Add some package extras to install optional dependencies (via `pip install`):
    * `requests-cache[all]` (to install everything)
    * `requests-cache[bson]`
    * `requests-cache[json]`
    * `requests-cache[dynamodb]`
    * `requests-cache[mongodb]`
    * `requests-cache[redis]`

**Compatibility and packaging:**
* Fix some compatibility issues with `requests 2.17` and `2.18`
* Run pre-release tests for each supported version of `requests`
* Packaging is now handled with Poetry. For users, installation still works the same. For developers, see [Contributing Guide](https://requests-cache.readthedocs.io/en/stable/contributing.html) for details


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

Thanks to [Code Shelter](https://www.codeshelter.co) and [contributors](https://requests-cache.readthedocs.io/en/stable/contributors.html) for making this release possible!

**Backends:**
* SQLite: Allow passing user paths (`~/path-to-cache`) to database file with `db_path` param
* SQLite: Add `timeout` parameter
* Make default table names consistent across backends (`'http_cache'`)

**Expiration:**
* Cached responses are now stored with an absolute expiration time, so `CachedSession.expire_after` no longer applies retroactively. To revalidate previously cached items with a new expiration time see below:
* Add support for overriding original expiration (i.e., revalidating) in `CachedSession.remove_expired_responses()`
* Add support for setting expiration for individual requests
* Add support for setting expiration based on URL glob patterns
* Add support for setting expiration as a `datetime`
* Add support for explicitly disabling expiration with `-1` (Since `None` may be ambiguous in some cases)

**Serialization:**
* **Note:** Due to the following changes, responses cached with previous versions of requests-cache will be invalid. These **old responses will be treated as expired**, and will be refreshed the next time they are requested. They can also be manually converted or removed, if needed (see notes below).
* Add [example script](https://github.com/reclosedev/requests-cache/blob/master/examples/convert_cache.py) to convert an existing cache from previous serialization format to new one
* When running `remove_expired_responses()`, also remove responses that are invalid due to updated serialization format
* Add `CachedResponse` class to wrap cached `requests.Response` objects, which makes additional cache information available to client code
* Add `CachedHTTPResponse` class to wrap `urllib3.response.HTTPResponse` objects, available via `CachedResponse.raw`
    * Re-construct the raw response on demand to avoid storing extra data in the cache
    * Improve emulation of raw request behavior used for iteration, streaming requests, etc.
* Add `BaseCache.urls` property to get all URLs persisted in the cache
* Add optional support for `itsdangerous` for more secure serialization

**Other features:**
* Add `CacheMixin` class to make the features of `CachedSession` usable as a mixin class, for [compatibility with other requests-based libraries](https://requests-cache.readthedocs.io/en/stable/advanced_usage.html#library-compatibility).
* Add `HEAD` to default `allowable_methods`

**Bugfixes:**
* Fix caching requests with data specified in `json` parameter
* Fix caching requests with `verify` parameter
* Fix duplicate cached responses due to some unhandled variations in URL format
* Fix usage of backend-specific params when used in place of `cache_name`
* Fix potential TypeError with `DbPickleDict` initialization
* Fix usage of `CachedSession.cache_disabled` if used within another contextmanager
* Fix non-thread-safe iteration in `BaseCache`
* Fix `get_cache()`, `clear()`, and `remove_expired_responses()` so they will do nothing if requests-cache is not installed
* Update usage of deprecated MongoClient `save()` method
* Replace some old bugs with new and different bugs, just to keep life interesting

**Depedencies:**
* Add `itsdangerous` as a dependency for secure serialization
* Add `url-normalize` as a dependency for better request normalization and reducing duplications

**Deprecations & removals:**
* Drop support for python 2.7, 3.4, and 3.5
* Deprecate `core` module; all imports should be made from top-level package instead
    * e.g.: `from requests_cache import CachedSession`
    * Imports `from requests_cache.core` will raise a `DeprecationWarning`, and will be removed in a future release
* Rename `BaseCache.remove_old_entries()` to `remove_expired_responses()`, to match its wrapper method `CachedSession.remove_expired_responses()`

**Docs & Tests:**
* Add type annotations to main functions/methods in public API, and include in documentation on [readthedocs](https://requests-cache.readthedocs.io/en/stable/)
* Add [Contributing Guide](https://requests-cache.readthedocs.io/en/stable/contributing.html), [Security](https://requests-cache.readthedocs.io/en/stable/security.html) info, and more examples & detailed usage info in [User Guide](https://requests-cache.readthedocs.io/en/stable/user_guide.html) and [Advanced Usage](https://requests-cache.readthedocs.io/en/stable/advanced_usage.html) sections.
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
* Drop support for python 2.6

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
