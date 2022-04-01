% Note: The module sources referenced here are auto-generated with apidoc
(reference)=
# {fa}`list` API Reference
This section covers all the public interfaces of requests-cache.

:::{tip}
It's recommended to import from the top-level `requests_cache` package, as internal module paths
may be subject to change. For example:
```python
from requests_cache import CachedSession, RedisCache, json_serializer
```
:::

## Primary Modules
The following modules include the majority of the API relevant for most users:

```{toctree}
:maxdepth: 2
session
modules/requests_cache.patcher
modules/requests_cache.backends
modules/requests_cache.models
modules/requests_cache.settings
```

## Secondary Modules
The following modules are mainly for internal use, and are relevant for contributors and advanced users:
```{toctree}
:maxdepth: 2
modules/requests_cache.cache_keys
modules/requests_cache.cache_control
modules/requests_cache.expiration
modules/requests_cache.serializers
```
