"""
.. image::
    ../_static/files-generic.png

This backend stores responses in files on the local filesystem (one file per response).

File Formats
^^^^^^^^^^^^
By default, responses are saved as pickle files, since this format is generally the fastest. If you
want to save responses in a human-readable format, you can use one of the other available
:ref:`serializers`. For example, to save responses as JSON files:

    >>> session = CachedSession('~/http_cache', backend='filesystem', serializer='json')
    >>> session.get('https://httpbin.org/get')
    >>> print(list(session.cache.paths()))
    ['/home/user/http_cache/4dc151d95200ec.json']

Or as YAML (requires ``pyyaml``):

    >>> session = CachedSession('~/http_cache', backend='filesystem', serializer='yaml')
    >>> session.get('https://httpbin.org/get')
    >>> print(list(session.cache.paths()))
    ['/home/user/http_cache/4dc151d95200ec.yaml']

Cache Files
^^^^^^^^^^^
* See :ref:`files` for general info on specifying cache paths
* The path for a given response will be in the format ``<cache_name>/<cache_key>``
* Redirects are stored in a separate SQLite database, located at ``<cache_name>/redirects.sqlite``
* Use :py:meth:`.FileCache.paths` to get a list of all cached response paths

API Reference
^^^^^^^^^^^^^
.. automodsumm:: requests_cache.backends.filesystem
   :classes-only:
   :nosignatures:
"""
from contextlib import contextmanager
from os import makedirs
from pathlib import Path
from pickle import PickleError
from shutil import rmtree
from threading import RLock
from typing import Iterator

from ..serializers import SERIALIZERS
from . import BaseCache, BaseStorage
from .sqlite import AnyPath, SQLiteDict, get_cache_path


class FileCache(BaseCache):
    """Filesystem backend.

    Args:
        cache_name: Base directory for cache files
        use_cache_dir: Store datebase in a user cache directory (e.g., `~/.cache/`)
        use_temp: Store cache files in a temp directory (e.g., ``/tmp/http_cache/``).
            Note: if ``cache_name`` is an absolute path, this option will be ignored.
        extension: Extension for cache files. If not specified, the serializer default extension
            will be used.
    """

    def __init__(self, cache_name: AnyPath = 'http_cache', use_temp: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.responses: FileDict = FileDict(cache_name, use_temp=use_temp, **kwargs)
        self.redirects: SQLiteDict = SQLiteDict(
            self.cache_dir / 'redirects.sqlite', 'redirects', **kwargs
        )

    @property
    def cache_dir(self) -> Path:
        """Base directory for cache files"""
        return Path(self.responses.cache_dir)

    def paths(self) -> Iterator[Path]:
        """Get absolute file paths to all cached responses"""
        return self.responses.paths()

    def clear(self):
        """Clear the cache"""
        # FileDict.clear() removes the cache directory, including redirects.sqlite
        self.responses.clear()
        self.redirects.init_db()

    def remove_expired_responses(self, *args, **kwargs):
        with self.responses._lock:
            return super().remove_expired_responses(*args, **kwargs)


class FileDict(BaseStorage):
    """A dictionary-like interface to files on the local filesystem"""

    def __init__(
        self,
        cache_name: AnyPath,
        use_temp: bool = False,
        use_cache_dir: bool = False,
        extension: str = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.cache_dir = get_cache_path(cache_name, use_cache_dir=use_cache_dir, use_temp=use_temp)
        self.extension = _get_extension(extension, self.serializer)
        self.is_binary = getattr(self.serializer, 'is_binary', False)
        self._lock = RLock()
        makedirs(self.cache_dir, exist_ok=True)

    @contextmanager
    def _try_io(self, ignore_errors: bool = False):
        """Attempt an I/O operation, and either ignore errors or re-raise them as KeyErrors"""
        try:
            with self._lock:
                yield
        except (EOFError, IOError, OSError, PickleError) as e:
            if not ignore_errors:
                raise KeyError(e)

    def _path(self, key) -> Path:
        return self.cache_dir / f'{key}{self.extension}'

    def __getitem__(self, key):
        mode = 'rb' if self.is_binary else 'r'
        with self._try_io():
            with self._path(key).open(mode) as f:
                return self.serializer.loads(f.read())

    def __delitem__(self, key):
        with self._try_io():
            self._path(key).unlink()

    def __setitem__(self, key, value):
        with self._try_io():
            with self._path(key).open(mode='wb' if self.is_binary else 'w') as f:
                f.write(self.serializer.dumps(value))

    def __iter__(self):
        yield from self.keys()

    def __len__(self):
        return sum(1 for _ in self.paths())

    def clear(self):
        with self._try_io(ignore_errors=True):
            rmtree(self.cache_dir, ignore_errors=True)
            self.cache_dir.mkdir()

    def keys(self):
        return [path.stem for path in self.paths()]

    def paths(self) -> Iterator[Path]:
        """Get absolute file paths to all cached responses"""
        with self._lock:
            return self.cache_dir.glob(f'*{self.extension}')


def _get_extension(extension: str = None, serializer=None) -> str:
    """Use either the provided file extension, or get the serializer's default extension"""
    if extension:
        return f'.{extension}'
    for name, obj in SERIALIZERS.items():
        if serializer is obj:
            return '.' + name.replace('pickle', 'pkl')
    return ''
