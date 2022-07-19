(examples)=
# {fas}`laptop-code` Examples
This section contains some complete examples that demonstrate the main features of requests-cache.

## Articles
Some articles and blog posts that discuss requests-cache:

* PyBites: [Module of the Week: requests-cache for repeated API calls](https://pybit.es/articles/requests-cache/)
* Real Python: [Caching External API Requests](https://realpython.com/blog/python/caching-external-api-requests)
* Thomas Gorham: [Faster Backtesting with requests-cache](https://www.mntn.dev/blog/requests-cache)
* Tim O'Hearn: [Pragmatic Usage of requests-cache](https://www.tjohearn.com/2018/02/12/pragmatic-usage-of-requests-cache/)
* Valdir Stumm Jr: [Tips for boosting your Python scripts](https://stummjr.org/post/building-scripts-in-python/)
* Python Web Scraping (2nd Edition): [Exploring requests-cache](https://learning.oreilly.com/library/view/python-web-scraping/9781786462589/3fad0dcc-445b-49a4-8d5e-ba5e1ff8e3bb.xhtml)
* Cui Qingcai: [一个神器，大幅提升爬取效率](https://cuiqingcai.com/36052.html) (A package that greatly improves crawling efficiency)

<!--
Explicit line numbers are added below to include the module docstring in the main doc, and put the
rest of the module contents in a dropdown box.
TODO: It might be nice to have a custom extension to do this automatically.
-->
## Scripts
The following scripts can also be found in the
[examples/](https://github.com/requests-cache/requests-cache/tree/main/examples) folder on GitHub.

### Basic usage (with sessions)
```{include} ../examples/basic_sessions.py
:start-line: 3
:end-line: 4
```

:::{dropdown} Example
:animate: fade-in-slide-down
:color: primary
:icon: file-code

[basic_sessions.py](https://github.com/requests-cache/requests-cache/blob/main/examples/basic_sessions.py)
```{literalinclude} ../examples/basic_sessions.py
:lines: 6-
```
:::

### Basic usage (with patching)
```{include} ../examples/basic_patching.py
:start-line: 3
:end-line: 4
```

:::{dropdown} Example
:animate: fade-in-slide-down
:color: primary
:icon: file-code

[basic_patching.py](https://github.com/requests-cache/requests-cache/blob/main/examples/basic_patching.py)
```{literalinclude} ../examples/basic_patching.py
:lines: 6-
```
:::

### Cache expiration
```{include} ../examples/expiration.py
:start-line: 2
:end-line: 3
```

:::{dropdown} Example
:animate: fade-in-slide-down
:color: primary
:icon: file-code

[expiration.py](https://github.com/requests-cache/requests-cache/blob/main/examples/expiration.py)
```{literalinclude} ../examples/expiration.py
:lines: 5-
```
:::

### URL patterns
```{include} ../examples/url_patterns.py
:start-line: 3
:end-line: 4
```

:::{dropdown} Example
:animate: fade-in-slide-down
:color: primary
:icon: file-code

[url_patterns.py](https://github.com/requests-cache/requests-cache/blob/main/examples/url_patterns.py)
```{literalinclude} ../examples/url_patterns.py
:lines: 6-
```
:::

### PyGithub
```{include} ../examples/pygithub.py
:start-line: 2
:end-line: 25
```

:::{dropdown} Example
:animate: fade-in-slide-down
:color: primary
:icon: file-code

[pygithub.py](https://github.com/requests-cache/requests-cache/blob/main/examples/pygithub.py)
```{literalinclude} ../examples/pygithub.py
:lines: 27-
```
:::

### Multi-threaded requests
```{include} ../examples/threads.py
:start-line: 2
:end-line: 4
```

:::{dropdown} Example
:animate: fade-in-slide-down
:color: primary
:icon: file-code

[threads.py](https://github.com/requests-cache/requests-cache/blob/main/examples/threads.py)
```{literalinclude} ../examples/threads.py
:lines: 6-
```
:::

### Logging requests
```{include} ../examples/log_requests.py
:start-line: 2
:end-line: 3
```

:::{dropdown} Example
:animate: fade-in-slide-down
:color: primary
:icon: file-code

[log_requests.py](https://github.com/requests-cache/requests-cache/blob/main/examples/log_requests.py)
```{literalinclude} ../examples/log_requests.py
:lines: 5-
```
:::

### External configuration
```{include} ../examples/external_config.py
:start-line: 2
:end-line: 8
```

:::{dropdown} Example
:animate: fade-in-slide-down
:color: primary
:icon: file-code

[external_config.py](https://github.com/requests-cache/requests-cache/blob/main/examples/external_config.py)
```{literalinclude} ../examples/external_config.py
:lines: 10-
```
:::

### Cache speed test
```{include} ../examples/benchmark.py
:start-line: 2
:end-line: 8
```

:::{dropdown} Example
:animate: fade-in-slide-down
:color: primary
:icon: file-code

[benchmark.py](https://github.com/requests-cache/requests-cache/blob/main/examples/benchmark.py)
```{literalinclude} ../examples/benchmark.py
:lines: 10-
```
:::

### Using with GitHub Actions
This example shows how to use requests-cache with [GitHub Actions](https://docs.github.com/en/actions).
Key points:
* Create the cache file within the CI project directory
* You can use [actions/cache](https://github.com/actions/cache) to persist the cache file across
  workflow runs
    * You can use a constant cache key within this action to let requests-cache handle expiration


:::{dropdown} Example
:animate: fade-in-slide-down
:color: primary
:icon: file-code

[github_actions.yml](https://github.com/requests-cache/requests-cache/blob/main/examples/github_actions.yml)
```{literalinclude} ../examples/github_actions.yml
```
:::

### Converting an old cache
```{include} ../examples/convert_cache.py
:start-line: 2
:end-line: 4
```

:::{dropdown} Example
:animate: fade-in-slide-down
:color: primary
:icon: file-code

[convert_cache.py](https://github.com/requests-cache/requests-cache/blob/main/examples/convert_cache.py)
```{literalinclude} ../examples/convert_cache.py
:lines: 6-
```
:::

(custom_keys)=
### Custom request matcher
```{include} ../examples/custom_request_matcher.py
:start-line: 2
:end-line: 15
```

:::{dropdown} Example
:animate: fade-in-slide-down
:color: primary
:icon: file-code

[custom_request_matcher.py](https://github.com/requests-cache/requests-cache/blob/main/examples/custom_request_matcher.py)
```{literalinclude} ../examples/custom_request_matcher.py
:lines: 17-
```
:::


### Backtesting with time-machine
```{include} ../examples/time_machine_backtesting.py
:start-line: 2
:end-line: 4
```

:::{dropdown} Example
:animate: fade-in-slide-down
:color: primary
:icon: file-code

[time_machine_backtesting.py](https://github.com/requests-cache/requests-cache/blob/main/examples/time_machine_backtesting.py)
```{literalinclude} ../examples/time_machine_backtesting.py
:lines: 6-
```
:::


### VCR Export
```{include} ../examples/vcr.py
:start-line: 2
:end-line: 5
```

:::{dropdown} Example
:animate: fade-in-slide-down
:color: primary
:icon: file-code

[vcr.py](https://github.com/requests-cache/requests-cache/blob/main/examples/vcr.py)
```{literalinclude} ../examples/vcr.py
:lines: 7-
```
:::
