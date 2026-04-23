(security)=
# {fas}`lock` Security
This page contains some security recommendations and guidelines for advanced use cases.

## Shared Server Environment
requests-cache is mainly intended for use as a **private, client-side, single-user cache**,
analogous to a browser cache. It should not be used as a public/proxy cache (like Squid or Varnish).
For a purely server-side use case (i.e., caching responses to incoming requests), your best option
will likely be a purpose-built {ref}`server cache <server-cache>` that integrates with your web
framework of choice.

Applications that are both HTTP clients and servers can use requests-cache, but some extra
consideration is required. In particular, if your server is shared among multiple principals (users,
applications, tenants, etc.), you will need to consider the following:

(default-filter-params)=
### Removing Sensitive Info
The {ref}`ignored_parameters <filter-params>` option can be used to prevent credentials and other
sensitive info from being saved to the cache. It applies to request parameters, body (JSON or form
encoding), and headers. Ignored params will be both omitted from request matching and redacted from
the cache.

Some are ignored by default, including:
* `Authorization` header (most authentication systems)
* `access_token` request param (used by OAuth)
* `access_token` in POST body (used by OAuth)
* `api_key` request param (used by OpenAPI spec)
* `X-API-KEY` header (used by OpenAPI spec)
* `X-Access-Token`/`X-Auth-Token` headers (some JWT implementations)

To explicitly ignore + redact a different parameter or header:
```python
>>> from requests_cache import CachedSession
>>> session = CachedSession(ignored_parameters=['X-Nonstandard-Credential'])
```

To append to the default list instead of replacing it:
```python
>>> from requests_cache import CachedSession, DEFAULT_IGNORED_PARAMS
>>> ignored_parameters = list(DEFAULT_IGNORED_PARAMS) + ['X-Nonstandard-Credential']
>>> session = CachedSession(ignored_parameters=ignored_parameters)
```

However, there are cases where you would _not_ want to exclude this information from the cache;
see section below.

### Auth-gated content
:::{warning}
Authenticated requests for multiple users must be handled carefully to avoid exposing authenticated
content from one user (or other principal) to an unintended one.
:::

This can happen if there is no {ref}`matching` information available to distinguish one user's
request from another. Since requests-cache only operates at the HTTP level, it has no knowledge of
users or other app/framework-specific request context, aside from what is passed via request params
and headers.

To protect against the most common cases of this, requests-cache will refuse to serve a cached
request containing a header that is in both `ignored_parameters` and `Vary` (for example,
`Authorization` + `Vary: Authorization`).

It's preferable to handle this proactively in your application, though. Options include:
* Use a separate cache per user
* Exclude authenticated requests completely (via any combination of {ref}`filtering` features)
* Pass additional headers or params solely for request matching purposes
* Always match on authentication headers using `match_headers` and (if applicable) overriding
  `ignored_parameters`. If your cache backend is secured, you can choose to not redact auth
  headers/params from the cache.

Example: In the case of `Authorization` with a JWT, this would make the tradeoff of storing the
token in the cache but making it usable for request matching (i.e., store a separate cached response
per token value).
```python
session = CachedSession(
    match_headers=['Authorization'],  # Make this part of the cache key, even if not specified by Vary
    ignored_parameters=[],            # Remove it from default ignored/redacted params
)
```

## Pickle Vulnerabilities
:::{warning}
The python `pickle` module has [known security vulnerabilities](https://docs.python.org/3/library/pickle.html),
potentially leading to code execution when deserializing data.

This means it should only be used to deserialize data that you trust hasn't been tampered with.
:::

### Safe Pickling With Untrusted Data
If you're working with untrusted data, consider using one of the other supported {ref}`serializers`
instead of pickle.

Since this isn't always possible, requests-cache can optionally use
[itsdangerous](https://itsdangerous.palletsprojects.com) to add a layer of security around these operations.
It works by signing serialized data with a secret key that you control. Then, if the data is tampered
with, the signature check fails and raises an error.

Optional dependencies can be installed with:
```bash
pip install itsdangerous
```

### Creating and Storing a Secret Key
To enable this behavior, first create a secret key, which can be any `str` or `bytes` object.

One common pattern for handling this is to store it wherever you store the rest of your credentials
([Linux keyring](https://itsfoss.com/ubuntu-keyring),
[macOS keychain](https://support.apple.com/guide/mac-help/use-keychains-to-store-passwords-mchlf375f392/mac),
[password database](https://keepassxc.org), etc.),
set it in an environment variable, and then read it in your application:
```python
>>> import os
>>> secret_key = os.environ['SECRET_KEY']
```

Alternatively, you can use the [keyring](https://keyring.readthedocs.io) package to read the key
directly:
```python
>>> import keyring
>>> secret_key = keyring.get_password('requests-cache-example', 'secret_key')
```

### Signing Cached Responses
Once you have your key, create a {py:func}`.safe_pickle_serializer` with it:
```python
>>> from requests_cache import CachedSession, safe_pickle_serializer
>>> serializer = safe_pickle_serializer(secret_key=secret_key)
>>> session = CachedSession(serializer=serializer)
>>> session.get('https://httpbin.org/get')
```

:::{note}
You can also make your own {ref}`custom-serializers`, if you would like more control over how
responses are serialized.
:::

You can verify that it's working by modifying the cached item (*without* your key):
```python
>>> serializer_2 = safe_pickle_serializer(secret_key='a different key')
>>> session_2 = CachedSession(serializer=serializer_2)
>>> cache_key = list(session_2.cache.responses.keys())[0]
>>> session_2.cache.responses[cache_key] = 'exploit!'
```

Then, if you try to get that cached response again (*with* your key), you will get an error:
```python
>>> session.get('https://httpbin.org/get')
BadSignature: Signature b'iFNmzdUOSw5vqrR9Cb_wfI1EoZ8' does not match
```
