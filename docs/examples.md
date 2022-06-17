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

:::{admonition} Example: [basic_sessions.py](https://github.com/requests-cache/requests-cache/blob/main/examples/basic_sessions.py)
:class: toggle
```{literalinclude} ../examples/basic_sessions.py
:lines: 6-
```
:::

### Basic usage (with patching)
```{include} ../examples/basic_patching.py
:start-line: 3
:end-line: 4
```

:::{admonition} Example: [basic_patching.py](https://github.com/requests-cache/requests-cache/blob/main/examples/basic_patching.py)
:class: toggle
```{literalinclude} ../examples/basic_patching.py
:lines: 6-
```
:::

### Cache expiration
```{include} ../examples/expiration.py
:start-line: 2
:end-line: 3
```

:::{admonition} Example: [expiration.py](https://github.com/requests-cache/requests-cache/blob/main/examples/expiration.py)
:class: toggle
```{literalinclude} ../examples/expiration.py
:lines: 5-
```
:::

### URL patterns
```{include} ../examples/url_patterns.py
:start-line: 3
:end-line: 4
```

:::{admonition} Example: [url_patterns.py](https://github.com/requests-cache/requests-cache/blob/main/examples/url_patterns.py)
:class: toggle
```{literalinclude} ../examples/url_patterns.py
:lines: 6-
```
:::

### PyGithub
```{include} ../examples/pygithub.py
:start-line: 2
:end-line: 25
```

:::{admonition} Example: [pygithub.py](https://github.com/requests-cache/requests-cache/blob/main/examples/pygithub.py)
:class: toggle
```{literalinclude} ../examples/pygithub.py
:lines: 27-
```
:::

### Multi-threaded requests
```{include} ../examples/threads.py
:start-line: 2
:end-line: 4
```

:::{admonition} Example: [threads.py](https://github.com/requests-cache/requests-cache/blob/main/examples/threads.py)
:class: toggle
```{literalinclude} ../examples/threads.py
:lines: 6-
```
:::

### Logging requests
```{include} ../examples/log_requests.py
:start-line: 2
:end-line: 3
```

:::{admonition} Example: [log_requests.py](https://github.com/requests-cache/requests-cache/blob/main/examples/log_requests.py)
:class: toggle
```{literalinclude} ../examples/log_requests.py
:lines: 5-
```
:::

### External configuration
```{include} ../examples/external_config.py
:start-line: 2
:end-line: 8
```

:::{admonition} Example: [external_config.py](https://github.com/requests-cache/requests-cache/blob/main/examples/external_config.py)
:class: toggle
```{literalinclude} ../examples/external_config.py
:lines: 10-
```
:::

### Cache speed test
```{include} ../examples/benchmark.py
:start-line: 2
:end-line: 8
```

:::{admonition} Example: [benchmark.py](https://github.com/requests-cache/requests-cache/blob/main/examples/benchmark.py)
:class: toggle
```{literalinclude} ../examples/benchmark.py
:lines: 10-
```
:::

### Converting an old cache
```{include} ../examples/convert_cache.py
:start-line: 2
:end-line: 4
```

:::{admonition} Example: [convert_cache.py](https://github.com/requests-cache/requests-cache/blob/main/examples/convert_cache.py)
:class: toggle
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

:::{admonition} Example: [custom_request_matcher.py](https://github.com/requests-cache/requests-cache/blob/main/examples/custom_request_matcher.py)
:class: toggle
```{literalinclude} ../examples/custom_request_matcher.py
:lines: 17-
```
:::


### Backtesting with time-machine
```{include} ../examples/time_machine_backtesting.py
:start-line: 2
:end-line: 4
```

:::{admonition} Example: [time_machine_backtesting.py](https://github.com/requests-cache/requests-cache/blob/main/examples/time_machine_backtesting.py)
:class: toggle
```{literalinclude} ../examples/time_machine_backtesting.py
:lines: 6-
```
:::


### VCR Export
```{include} ../examples/vcr.py
:start-line: 2
:end-line: 5
```

:::{admonition} Example: [vcr.py](https://github.com/requests-cache/requests-cache/blob/main/examples/vcr.py)
:class: toggle
```{literalinclude} ../examples/vcr.py
:lines: 7-
```
:::
