(related-projects)=
# {fas}`external-link-alt` Related Projects
If requests-cache isn't quite what you need, you can help make it better! See the
{ref}`Contributing Guide <contributing>` for details.

For other use cases, you can check out these other python projects related to caching:

## Client-side HTTP caching
* [aiohttp-client-cache](https://github.com/requests-cache/aiohttp-client-cache): An async HTTP cache for `aiohttp`, based on `requests-cache`
* [CacheControl](https://github.com/psf/cachecontrol): An HTTP cache that ports features from `httplib2` for usage with `requests`
* [Hishel](https://github.com/karpetrosyan/hishel): A sync+async HTTP cache for `httpx`

(server-cache)=
## Server-side HTTP caching
* [aiohttp-cache](https://github.com/cr0hn/aiohttp-cache): A server-side async HTTP cache for the `aiohttp` web server
* [django cache](https://docs.djangoproject.com/en/stable/topics/cache/): Built-in server-side caching for Django applications
* [fastapi-cache](https://github.com/long2ice/fastapi-cache): A server-side async HTTP cache for applications built with FastAPI
* [flask-caching](https://github.com/pallets-eco/flask-caching): A server-side HTTP cache for applications built with Flask
* [starlette-caches](https://github.com/mattmess1221/starlette-caches): HTTP caching middleware for Starlette/FastAPI, inspired by Django's cache framework

## General
* [aiocache](https://github.com/aio-libs/aiocache): General-purpose async cache backends
* [cachier](https://github.com/python-cachier/cachier): A general-purpose cache with file-based and MongoDB backends
* [cachetools](https://github.com/tkem/cachetools): Memoizing collections and decorators with LRU, TTL, FIFO, and other eviction strategies
* [diskcache](https://github.com/grantjenks/python-diskcache): A general-purpose file-based cache built on SQLite
* [dogpile.cache](https://github.com/sqlalchemy/dogpile.cache): A caching frontend with concurrency locking and backends for Redis, Memcached, and databases

## Testing
* [requests-mock](https://github.com/jamielennox/requests-mock): A `requests` transport adapter that mocks HTTP responses
* [responses](https://github.com/getsentry/responses): A utility for mocking out the `requests` library
* [vcrpy](https://github.com/kevin1024/vcrpy): Records responses to local files and plays them back for tests; inspired by Ruby's [VCR](https://github.com/vcr/vcr). Works at the `httplib` level and is compatible with multiple HTTP libraries.
* [betamax](https://github.com/betamaxpy/betamax): Records responses to local files and plays them back for tests; inspired by Ruby's [VCR](https://github.com/vcr/vcr). Made specifically for `requests`.
* [HTTPretty](https://github.com/gabrielfalcao/HTTPretty): HTTP Client mocking tool that provides a full fake TCP socket module; inspired by Ruby's [FakeWeb](https://github.com/chrisk/fakeweb).
* [aioresponses](https://github.com/pnuckowski/aioresponses): A helper to mock web requests in `aiohttp`, inspired by `responses`
* [aresponses](https://github.com/aresponses/aresponses): An asyncio testing server for mocking external services
* [pook](https://github.com/h2non/pook): HTTP traffic mocking with support for `requests`, `aiohttp`, and `httpx`
