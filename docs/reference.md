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

<!--
TODO:
* move rst backend docs to md
* Copy/overwrite from extra_modules/ to modules/
-->
## Primary Modules
The following modules include the majority of the API relevant for most users:

```{toctree}
:maxdepth: 2
modules/requests_cache.session
modules/requests_cache.patcher
modules/requests_cache.backends
modules/requests_cache.models
```

## Secondary Modules
The following modules are mainly for internal use, and are relevant for contributors and advanced users:
```{toctree}
:maxdepth: 2
modules/requests_cache.cache_keys
modules/requests_cache.policy
modules/requests_cache.serializers
```
