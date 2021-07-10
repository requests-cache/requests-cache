(security)=
# Security

## Pickle Vulnerabilities
:::{warning}
The python `pickle` module has [known security vulnerabilities](https://docs.python.org/3/library/pickle.html),
potentially leading to code execution when deserialzing data.
:::

This means it should only be used to deserialize data that you trust hasn't been tampered with.
Since this isn't always possible, requests-cache can optionally use
[itsdangerous](https://itsdangerous.palletsprojects.com) to add a layer of security around these operations.
It works by signing serialized data with a secret key that you control. Then, if the data is tampered
with, the signature check fails and raises an error.

## Creating and Storing a Secret Key
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

## Signing Cached Responses
Once you have your key, create a {py:func}`.safe_pickle_serializer` with it:
```python
>>> from requests_cache import CachedSession, safe_pickle_serializer
>>> serializer = safe_pickle_serializer(secret_key=secret_key)
>>> session = CachedSession(serializer=serializer)
>>> session.get('https://httpbin.org/get')
```

:::{note}
You can also make your own {ref}`custom serializer <advanced_usage:custom serializers>`
using `itsdangerous`, if you would like more control over how responses are serialized.
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
