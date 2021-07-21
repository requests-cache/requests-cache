% Note: backend and serializer module docs are auto-generated with apidoc;
% the remaining modules are manually added here for more custom formatting.
(reference)=
# API Reference
This section covers all the public interfaces of requests-cache.

## Sessions
% Explicitly show inherited method docs on CachedSession instead of CachedMixin
```{eval-rst}
.. autoclass:: requests_cache.session.CachedSession
    :members: send, request, cache_disabled, remove_expired_responses
    :show-inheritance:
```

```{eval-rst}
.. autoclass:: requests_cache.session.CacheMixin
```

## Patching
```{eval-rst}
.. automodule:: requests_cache.patcher
    :members:
```

## Cache Backends
```{toctree}
modules/requests_cache.backends
```

## Models
```{toctree}
modules/requests_cache.models
```

## Serializers
```{toctree}
modules/requests_cache.serializers
```

## Utilities
```{toctree}
utilities
```