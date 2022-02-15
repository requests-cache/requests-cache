(examples)=
# {fa}`laptop-code,style=fas` Examples
This section contains some complete examples that demonstrate the main features of requests-cache.

## Articles
Some articles and blog posts that discuss requests-cache:

* PyBites: [Module of the Week: requests-cache for repeated API calls](https://pybit.es/articles/requests-cache/)
* Real Python: [Caching External API Requests](https://realpython.com/blog/python/caching-external-api-requests)
* Thomas Gorham: [Faster Backtesting with requests-cache](https://www.mntn.dev/blog/requests-cache)
* Tim O'Hearn: [Pragmatic Usage of requests-cache](https://www.tjohearn.com/2018/02/12/pragmatic-usage-of-requests-cache/)
* Valdir Stumm Jr: [Tips for boosting your Python scripts](https://stummjr.org/post/building-scripts-in-python/)
* Python Web Scraping (2nd Edition): [Exploring requests-cache](https://learning.oreilly.com/library/view/python-web-scraping/9781786462589/3fad0dcc-445b-49a4-8d5e-ba5e1ff8e3bb.xhtml)

## Scripts
The following scripts can also be found in the
[examples/](https://github.com/reclosedev/requests-cache/tree/master/examples) folder on GitHub.

### Basic usage (with sessions)
```{include} ../examples/basic_sessions.py
:start-line: 3
:end-line: 4
```

:::{admonition} Example: basic_sessions.py
:class: toggle
```{literalinclude} ../examples/basic_sessions.py
:lines: 1,6-
```
:::

### Basic usage (with patching)
```{include} ../examples/basic_patching.py
:start-line: 3
:end-line: 4
```

:::{admonition} Example: basic_patching.py
:class: toggle
```{literalinclude} ../examples/basic_patching.py
:lines: 1,6-
```
:::

### Cache expiration
```{include} ../examples/expiration.py
:start-line: 2
:end-line: 3
```

:::{admonition} Example: expiration.py
:class: toggle
```{literalinclude} ../examples/expiration.py
:lines: 1,5-
```
:::

### URL patterns
```{include} ../examples/url_patterns.py
:start-line: 3
:end-line: 4
```

:::{admonition} Example: /url_patterns.py
:class: toggle
```{literalinclude} ../examples/url_patterns.py
:lines: 1,6-
```
:::

### Multi-threaded requests
```{include} ../examples/threads.py
:start-line: 2
:end-line: 4
```

:::{admonition} Example: threads.py
:class: toggle
```{literalinclude} ../examples/threads.py
:lines: 1,6-
```
:::

### Logging requests
```{include} ../examples/log_requests.py
:start-line: 2
:end-line: 3
```

:::{admonition} Example: log_requests.py
:class: toggle
```{literalinclude} ../examples/log_requests.py
:lines: 1,5-
```
:::

### Cache speed test
```{include} ../examples/benchmark.py
:start-line: 2
:end-line: 8
```

:::{admonition} Example: benchmark.py
:class: toggle
```{literalinclude} ../examples/benchmark.py
:lines: 1,10-
```
:::

### Converting an old cache
```{include} ../examples/convert_cache.py
:start-line: 2
:end-line: 4
```

:::{admonition} Example: convert_cache.py
:class: toggle
```{literalinclude} ../examples/convert_cache.py
:lines: 1,6-
```
:::

(custom_keys)=
### Custom request matcher
```{include} ../examples/custom_request_matcher.py
:start-line: 2
:end-line: 15
```

:::{admonition} Example: custom_request_matcher.py
:class: toggle
```{literalinclude} ../examples/custom_request_matcher.py
:lines: 1,17-
```
:::


### Backtesting with time-machine
```{include} ../examples/time_machine_backtesting.py
:start-line: 2
:end-line: 4
```

:::{admonition} Example: custom_request_matcher.py
:class: toggle
```{literalinclude} ../examples/time_machine_backtesting.py
:lines: 1,6-
```
:::
