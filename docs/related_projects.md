# Related Projects
If requests-cache isn't quite what you need, you can help make it better! See the
{ref}`Contributing Guide <contributing>` for details.

You can also check out these other python projects related to caching and/or HTTP requests:

## General
* [CacheControl](https://github.com/ionrock/cachecontrol): An HTTP cache for `requests` that caches
  according to HTTP headers
* [diskcache](https://github.com/grantjenks/python-diskcache): A general-purpose (not HTTP-specific)
  file-based cache built on SQLite

## Async
* [aiohttp-client-cache](https://github.com/JWCook/aiohttp-client-cache): An async HTTP cache for
  `aiohttp`, based on `requests-cache`
* [aiohttp-cache](https://github.com/cr0hn/aiohttp-cache): A server-side async HTTP cache for the
  `aiohttp` web server
* [aiocache](https://github.com/aio-libs/aiocache): General-purpose (not HTTP-specific) async cache
  backends

## Other web frameworks
* [flask-caching](https://github.com/sh4nks/flask-caching): A server-side HTTP cache for
  applications using the Flask framework

## Testing
* [requests-mock](https://github.com/jamielennox/requests-mock): A `requests` transport adapter that
  mocks HTTP responses
* [responses](https://github.com/getsentry/responses): A utility for mocking out the `requests` library
* [vcrpy](https://github.com/kevin1024/vcrpy): Records responses to local files and plays them back
  for tests; inspired by Ruby's [VCR](https://github.com/vcr/vcr)]. Works at the `httplib` level and
  is compatible with multiple HTTP libraries.
* [betamax](https://github.com/betamaxpy/betamax): Records responses to local files and plays them back
  for tests; also inspired by Ruby's [VCR](https://github.com/vcr/vcr)]. Made specifically for `requests`.
