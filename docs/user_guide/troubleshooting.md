(debug)=
# {fa}`exclamation-circle` Troubleshooting
Here are a few tips for avoiding and debugging some common problems.

## General Tips
* Make sure you're using the latest version: `pip install -U requests-cache`
* Try [searching issues](https://github.com/reclosedev/requests-cache/issues?q=is%3Aissue+label%3Abug)
  for similar problems
* Enable debug logging to get more information
* If you have a problem and [figure it out yourself](https://xkcd.com/979/), it's likely that
  someone else will have the same problem. It can be helpful to create an issue on GitHub just for
  reference, or submit a PR to add some notes to this page.

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

## Potential Issues
* **Patching:** See {ref}`monkeypatch-issues` for notes specific to {py:func}`.install_cache`
* **Imports:** It's recommended to make all your imports from the top-level `requests_cache` package:
  ```python
  from requests_cache import x
  ```
* **Cache settings:** Some issues may be caused by changing settings for an existing cache. This is
  only likely to happen with some of the more advanced features like {ref}`custom-serializers` and
  {ref}`custom-matching`. In these cases, the easiest way to resolve the issue is to clear the cache
  with {py:meth}`CachedSession.cache.clear() <.BaseCache.clear>`.
* **Library updates:** New releases of `requests`, `urllib3` or `requests-cache` itself can
  potentially change response data, and be incompatible with previously cached responses. See issues
  [#56](https://github.com/reclosedev/requests-cache/issues/56) and
  [#102](https://github.com/reclosedev/requests-cache/issues/102).
  ```{note}
  A cached response that can't be reused will simply be deleted and fetched again. If you get a
  traceback just by reading from the cache, this is **not** intended behavior, so please create a bug
  report!
  ```

## Common Error Messages
Here are some error messages you may see either in the logs or (more rarely) in a traceback:

* **`Unable to deserialize response with key {cache key}`:** This
  usually means that a response was previously cached in a format that isn't compatible with the
  current version of requests-cache or one of its dependencies. It could also be the result of switching {ref}`serializers`.
  * This message is to help with debugging and can generally be ignored. If you prefer, you can
    either {py:meth}`~.BaseCache.clear` the cache or {py:meth}`~.BaseCache.remove_expired_responses`
    to get rid of the invalid responses.
* **`Request for URL {url} failed; using cached response`:** This is just a notification that the
  {ref}`stale_if_error <request-errors>` option is working as intended
* **{py:exc}`~requests.RequestException`:** These are general request errors not specific to
  requests-cache. See `requests` documentation on
  [Errors and Exceptions](https://2.python-requests.org/en/master/user/quickstart/#errors-and-exceptions)
  for more details.
* **{py:exc}`ModuleNotFoundError`**: `No module named 'requests_cache.core'`: This module was deprecated in `v0.6` and removed in `v0.8`. Just import from `requests_cache` instead of `requests_cache.core`.
* **{py:exc}`ImportError`:** Indicates a missing required or optional dependency.
  * If you see this at **import time**, it means that one or more **required** dependencies are not
    installed
  * If you see this at **runtime** or in a **log message**, it means that one or more **optional**
    dependencies are not installed
  * See {ref}`requirements` for details
* **{py:exc}`sqlite3.OperationalError`: `unable to open database file`** or **{py:exc}`IOError`:**
  This usually indicates a file permissions or ownership issue with either the database file or its parent directory.
* **{py:exc}`sqlite3.OperationalError`: `database is locked`:** This indicates a concurrency issue, and
  likely a bug. requests-cache + SQLite is intended to be thread-safe and multiprocess-safe, so
  please create a bug report if you encounter this.
* **{py:exc}`ResourceWarning`: `unclosed <ssl.SSLSocket ...>`:** This warning can **safely be ignored.**
  * This is normal behavior for {py:class}`requests.Session`, which uses connection pooling for better
    performance. In other words, these connections are intentionally left open to reduce the number of
    round-trips required for consecutive requests. For more details, see the following issues:
  * [requests/#3912: ResourceWarning: unclosed socket.socket when I run a unittest？](https://github.com/psf/requests/issues/3912)
  * [requests/#2963: ResourceWarning still triggered when warnings enabled](https://github.com/psf/requests/issues/2963#issuecomment-169631513)
  * [requests-cache/#413](https://github.com/reclosedev/requests-cache/issues/413)
  * If needed, this warning can be suppressed with:
    ```python
    import warnings

    warnings.simplefilter('ignore', ResourceWarning)
    ```

## Bug Reports
If you believe you've found a bug, or if you're just having trouble getting requests-cache to work
the way you want, please
[create an issue](https://github.com/reclosedev/requests-cache/issues/new/choose) for it on GitHub.

Details that will help your issue get resolved:
* A complete example to reproduce the issue
* Tracebacks and logging output
* Any other details about what you want to accomplish and how you want requests-cache to behave
