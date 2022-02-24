(headers)=
# {fa}`file-code` Cache Headers
Most common request and response headers related to caching are supported, including
[Cache-Control](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control)
and [ETags](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/ETag).

```{note}
requests-cache is not (yet) intended to be strict implementation of HTTP caching according to
[RFC 2616](https://datatracker.ietf.org/doc/html/rfc2616),
[RFC 7234](https://datatracker.ietf.org/doc/html/rfc7234), etc. If there is additional behavior you
would like to see, please create an issue to request it.
```

## Conditional Requests
[Conditional requests](https://developer.mozilla.org/en-US/docs/Web/HTTP/Conditional_requests) are
automatically sent for any servers that support them. Once a cached response expires, it will only
be updated if the remote content has changed.

Here's an example using the [GitHub API](https://docs.github.com/en/rest) to get info about the
requests-cache repo:
```python
>>> # Cache a response that will expire immediately
>>> url = 'https://api.github.com/repos/reclosedev/requests-cache'
>>> session = CachedSession(expire_after=0.0001)
>>> session.get(url)
>>> time.sleep(0.0001)

>>> # The cached response will still be used until the remote content actually changes
>>> response = session.get(url)
>>> print(response.from_cache, response.is_expired)
True, True
```

## Cache-Control
`Cache-Control` **request** headers will always be used if present. This is mainly useful if you are
adding requests-cache to an existing application or library that already uses caching request headers.

`Cache-Control` **response** headers are an opt-in feature. If enabled, these will take priority over
any other `expire_after` values. See {ref}`precedence` for the full order of precedence.
To enable this behavior, use the `cache_control` option:
```python
>>> session = CachedSession(cache_control=True)
```

## Supported Headers
The following headers are currently supported:

**Request headers:**
- `Cache-Control: max-age`: Used as the expiration time in seconds
- `Cache-Control: no-cache`: Skip reading from the cache
- `Cache-Control: no-store`: Skip reading from and writing to the cache
- `If-None-Match`: Automatically added if an `ETag` is available
- `If-Modified-Since`: Automatically added if `Last-Modified` is available

**Response headers:**
- `Cache-Control: max-age`: Used as the expiration time in seconds
- `Cache-Control: no-store` Skip writing to the cache
- `Cache-Control: immutable`: Cache the response with no expiration
- `Expires`: Used as an absolute expiration time
- `ETag`: Return expired cache data if the remote content has not changed (`304 Not Modified` response)
- `Last-Modified`: Return expired cache data if the remote content has not changed (`304 Not Modified` response)
