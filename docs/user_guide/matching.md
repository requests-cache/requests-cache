(matching)=
# {fas}`equals` Request Matching
Requests are matched according to the request method, URL, parameters and body. All of these values
are normalized to account for any variations that do not modify response content.

There are some additional options to configure how you want requests to be matched.

(filter-params)=
## Selective Parameter Matching
By default, all normalized request parameters are matched. In some cases, there may be request
parameters that you don't want to match. For example, an authentication token will change frequently
but not change reponse content.

Use the `ignored_parameters` option if you want to ignore specific parameters.

```{note}
Many common authentication parameters are already ignored by default.
See {ref}`default-filter-params` for details.
```

**Request Parameters:**

In this example, only the first request will be sent, and the second request will be a cache hit
due to the ignored parameters:
```python
>>> session = CachedSession(ignored_parameters=['auth-token'])
>>> session.get('https://httpbin.org/get', params={'auth-token': '2F63E5DF4F44'})
>>> r = session.get('https://httpbin.org/get', params={'auth-token': 'D9FAEB3449D3'})
>>> assert r.from_cache is True
```

**Request Body Parameters:**

This also applies to parameters in a JSON-formatted request body:
```python
>>> session = CachedSession(allowable_methods=('GET', 'POST'), ignored_parameters=['auth-token'])
>>> session.post('https://httpbin.org/post', json={'auth-token': '2F63E5DF4F44'})
>>> r = session.post('https://httpbin.org/post', json={'auth-token': 'D9FAEB3449D3'})
>>> assert r.from_cache is True
```

**Request Headers:**

As well as headers, if `match_headers=True` is used:
```python
>>> session = CachedSession(ignored_parameters=['auth-token'], match_headers=True)
>>> session.get('https://httpbin.org/get', headers={'auth-token': '2F63E5DF4F44'})
>>> r = session.get('https://httpbin.org/get', headers={'auth-token': 'D9FAEB3449D3'})
>>> assert r.from_cache is True
```
```{note}
Since `ignored_parameters` is most often used for sensitive info like credentials, these values will also be removed from the cached request parameters, body, and headers.
```

(matching-headers)=
## Matching Request Headers
```{note}
In some cases, request header values can affect response content. For example, sites that support
i18n and [content negotiation](https://developer.mozilla.org/en-US/docs/Web/HTTP/Content_negotiation) may use the `Accept-Language` header to determine which language to serve content in.

The server will ideally also send a `Vary` header in the response, which informs caches about
which request headers to match. By default, requests-cache respects this, so in many cases it
will already do what you want without extra configuration. Not all servers send `Vary`, however.
```

Use the `match_headers` option if you want to specify which headers you want to match when `Vary`
isn't available:
```python
>>> session = CachedSession(match_headers=['Accept'])
>>> # These two requests will be sent and cached separately
>>> session.get('https://httpbin.org/headers', {'Accept': 'text/plain'})
>>> session.get('https://httpbin.org/headers', {'Accept': 'application/json'})
```

If you want to match _all_ request headers, you can use `match_headers=True`.


(custom-matching)=
## Custom Request Matching
If you need more advanced behavior, you can implement your own custom request matching.

### Cache Keys
Request matching is accomplished using a **cache key**, which uniquely identifies a response in the
cache based on request info. For example, the option `ignored_parameters=['foo']` works by excluding
the `foo` request parameter from the cache key, meaning these three requests will all use the same
cached response:
```python
>>> session = CachedSession(ignored_parameters=['foo'])
>>> response_1 = session.get('https://example.com')          # cache miss
>>> response_2 = session.get('https://example.com?foo=bar')  # cache hit
>>> response_3 = session.get('https://example.com?foo=qux')  # cache hit
>>> assert response_1.cache_key == response_2.cache_key == response_3.cache_key
```

### Recreating Cache Keys
There are some situations where request matching behavior may change, which causes previously cached
responses to become obsolete:
* You start using a custom cache key, or change other settings that affect request matching
* A new version of requests-cache is released that includes new or changed request matching behavior
  (typically, most non-patch releases)

In these cases, if you want to keep using your existing cache data, you can use the
`recreate_keys` method:
```python
>>> session = CachedSession()
>>> session.cache.recreate_keys()
```

### Cache Key Functions
If you want to implement your own request matching, you can provide a cache key function which will
take a {py:class}`~requests.PreparedRequest` plus optional keyword args for
{py:func}`~requests.request`, and return a string:
```python
def create_key(request: requests.PreparedRequest, **kwargs) -> str:
    """Generate a custom cache key for the given request"""
```

You can then pass this function via the `key_fn` param:
```python
session = CachedSession(key_fn=create_key)
```

`**kwargs` includes relevant {py:class}`.BaseCache` settings and any other keyword args passed to
{py:meth}`.CachedSession.send()`. If you want use a custom matching function _and_ the existing
options `ignored_parameters` and `match_headers`, you can implement them in `key_fn`:
```python
def create_key(
    request: requests.PreparedRequest,
    ignored_parameters: List[str] = None,
    match_headers: List[str] = None,
    **kwargs,
) -> str:
    """Generate a custom cache key for the given request"""
```

See {py:func}`.create_key` for the reference implementation, and see the rest of the
{py:mod}`.cache_keys` module for some potentially useful helper functions.


```{tip}
See {ref}`Examples<custom_keys>` for a complete example for custom request matching.
```
```{tip}
As a general rule, if you include less information in your cache keys, you will have more cache hits
and use less storage space, but risk getting incorrect response data back.
```
```{warning}
If you provide a custom key function for a non-empty cache, any responses previously cached with a
different key function will be unused, so it's recommended to clear the cache first.
```

### Custom Header Normalization
When matching request headers (using `match_headers` or `Vary`), requests-cache will normalize minor
header variations like order, casing, whitespace, etc. In some cases, you may be able to further
optimize your requests with some additional header normalization.

For example, let's say you're working with a site that supports content negotiation using the
`Accept-Encoding` header, and the only varation you care about is whether you requested gzip
encoding. This example will increase cache hits by ignoring variations you don't care about:
```python
from requests import PreparedRequest
from requests_cache import CachedSession, create_key


def create_key(request: PreparedRequest, **kwargs) -> str:
    # Don't modify the original request that's about to be sent
    request = request.copy()

    # Simplify values like `Accept-Encoding: gzip, compress, br` to just `Accept-Encoding: gzip`
    if 'gzip' in request.headers.get('Accept-Encoding', ''):
        request.headers['Accept-Encoding'] = 'gzip'
    else:
        request.headers['Accept-Encoding'] = None

    # Use the default key function to do the rest of the work
    return create_key(request, **kwargs)


# Provide your custom request matcher when creating the session
session = CachedSession(key_fn=create_custom_key)
```
