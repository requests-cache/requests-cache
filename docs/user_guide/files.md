(files)=
# {fa}`folder-open` Cache Files
```{note}
This section only applies to the {py:mod}`SQLite <requests_cache.backends.sqlite>` and
{py:mod}`Filesystem <requests_cache.backends.filesystem>` backends.
```
For file-based backends, the cache name will be used as a path to the cache file(s). You can use
a relative path, absolute path, or use some additional options for system-specific default paths.

## Relative Paths
```python
>>> # Database path for SQLite cache
>>> session = CachedSession('http_cache', backend='sqlite')
>>> print(session.cache.db_path)
'<current working dir>/http_cache.sqlite'
```
```python
>>> # Base directory for Filesystem cache
>>> session = CachedSession('http_cache', backend='filesystem')
>>> print(session.cache.cache_dir)
'<current working dir>/http_cache/'
```

```{note}
Parent directories will always be created, if they don't already exist.
```

## Absolute Paths
You can also give an absolute path, including user paths (with `~`).
```python
>>> session = CachedSession('~/.myapp/http_cache', backend='sqlite')
>>> print(session.cache.db_path)
'/home/user/.myapp/http_cache.sqlite'
```

## System Paths
If you don't know exactly where you want to put your cache files, your system's **temp directory**
or **cache directory** is a good choice. Some options are available as shortcuts for these locations.

Use the default temp directory with the `use_temp` option:
:::{tab} Linux
```python
>>> session = CachedSession('http_cache', backend='sqlite', use_temp=True)
>>> print(session.cache.db_path)
'/tmp/http_cache.sqlite'
```
:::
:::{tab} macOS
```python
>>> session = CachedSession('http_cache', backend='sqlite', use_temp=True)
>>> print(session.cache.db_path)
'/var/folders/xx/http_cache.sqlite'
```
:::
:::{tab} Windows
```python
>>> session = CachedSession('http_cache', backend='sqlite', use_temp=True)
>>> print(session.cache.db_path)
'C:\\Users\\user\\AppData\\Local\\temp\\http_cache.sqlite'
```
:::

Or use the default cache directory with the `use_cache_dir` option:
:::{tab} Linux
```python
>>> session = CachedSession('http_cache', backend='filesystem', use_cache_dir=True)
>>> print(session.cache.cache_dir)
'/home/user/.cache/http_cache/'
```
:::
:::{tab} macOS
```python
>>> session = CachedSession('http_cache', backend='filesystem', use_cache_dir=True)
>>> print(session.cache.cache_dir)
'/Users/user/Library/Caches/http_cache/'
```
:::
:::{tab} Windows
```python
>>> session = CachedSession('http_cache', backend='filesystem', use_cache_dir=True)
>>> print(session.cache.cache_dir)
'C:\\Users\\user\\AppData\\Local\\http_cache\\'
```
:::

```{note}
If the cache name is an absolute path, the `use_temp` and `use_cache_dir` options will be ignored.
If it's a relative path, it will be relative to the temp or cache directory, respectively.
```

There are a number of other system default locations that might be appropriate for a cache file. See
the [appdirs](https://github.com/ActiveState/appdirs) library for an easy cross-platform way to get
the most commonly used ones.
