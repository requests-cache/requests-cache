(debug)=
# Troubleshooting
Here are a few tips for avoiding and debugging some common problems.

## Potential Issues
* **Patching:** See {ref}`monkeypatch-issues` for notes specific to {py:func}`.install_cache`
* **Imports:** It's recommended to import everything from the top-level `requests_cache` package.
  Other internal modules and utilities may change with future releases.
* **Library updates:** New releases of `requests`, `urllib3` or `requests-cache` itself can
  potentially change response data, and be incompatible with previously cached responses. See issues
  [#56](https://github.com/reclosedev/requests-cache/issues/56) and
  [#102](https://github.com/reclosedev/requests-cache/issues/102).
* **Cache settings:** Some issues may be caused by changing settings for an existing cache. For
  example, if you are using {ref}`custom-serializers`, {ref}`custom-matching`, or other advanced
  features, you may get unexpected behavior if you change those settings and reuse previously cached
  data. In these cases, the easiest way to resolve the issue is to clear the cache with
  ({py:meth}`CachedSession.cache.clear() <.BaseCache.clear>`).

```{note}
A cached response that can't be reused will simply be deleted and fetched again. If you get a
traceback just by reading from the cache, this is **not** intended behavior, so please create a bug
report!
```

## Logging
Debug logging can be enabled with the standard python `logging` module, for example with
{py:func}`logging.basicConfig`:
```python
import logging

logging.basicConfig(level='DEBUG')
```

For prettier, more readable logs, try the [rich](https://github.com/willmcgugan/rich) library's
[logging handler](https://rich.readthedocs.io/en/stable/logging.html):
```python
import logging
from rich.logging import RichHandler

logging.basicConfig(
    level='DEBUG', format="%(message)s", datefmt="[%X]", handlers=[RichHandler()]
)
```

If you have other libraries installed with verbose debug logging, you can configure only the loggers
you want with `logger.setLevel()`:
```python
import logging

logging.basicConfig(level='WARNING')
logging.getLogger('requests_cache').setLevel('DEBUG')
```

## Bug Reports
If you believe you've found a bug, or if you're just having trouble getting requests-cache to work
the way you want, please
[create an issue](https://github.com/reclosedev/requests-cache/issues/new/choose) for it on GitHub.

Details that will help your issue get resolved:
* A complete example to reproduce the issue
* Tracebacks and logging output
* Any other details about what you want to do and how you want it to work
