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
    >>> print(session.cache.paths())
    ['/home/user/http_cache/4dc151d95200ec.json']

Or as YAML (requires ``pyyaml``):

    >>> session = CachedSession('~/http_cache', backend='filesystem', serializer='yaml')
    >>> session.get('https://httpbin.org/get')
    >>> print(session.cache.paths())
    ['/home/user/http_cache/4dc151d95200ec.yaml']

Cache Files
^^^^^^^^^^^
* The path for a given response will be in the format ``<cache_name>/<cache_key>``
* Use :py:meth:`.FileCache.paths` to get a list of all cached response paths
* Redirects are stored in a separate SQLite database, located at ``<cache_name>/redirects.sqlite``
* See :py:mod:`~requests_cache.backends.sqlite` for more details on specifying paths

API Reference
^^^^^^^^^^^^^
.. automodsumm:: requests_cache.backends.filesystem
   :classes-only:
   :nosignatures:
"""
from contextlib import contextmanager
from glob import glob
from os import listdir, makedirs, unlink
from os.path import basename, join, splitext
from pathlib import Path
from pickle import PickleError
from shutil import rmtree
from typing import List, Union

from ..serializers import SERIALIZERS
from . import BaseCache, BaseStorage
from .sqlite import SQLiteDict, get_cache_path


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

    def __init__(self, cache_name: Union[Path, str] = 'http_cache', use_temp: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.responses = FileDict(cache_name, use_temp=use_temp, **kwargs)
        db_path = join(self.responses.cache_dir, 'redirects.sqlite')
        self.redirects = SQLiteDict(db_path, 'redirects', **kwargs)

    def paths(self) -> List[str]:
        """Get absolute file paths to all cached responses"""
        return self.responses.paths()

    def clear(self):
        """Clear the cache"""
        # FileDict.clear() removes and re-creates the cache directory, including redirects.sqlite
        self.responses.clear()
        self.redirects.init_db()


class FileDict(BaseStorage):
    """A dictionary-like interface to files on the local filesystem"""

    def __init__(
        self,
        cache_name,
        use_temp: bool = False,
        use_cache_dir: bool = False,
        extension: str = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.cache_dir = get_cache_path(cache_name, use_cache_dir=use_cache_dir, use_temp=use_temp)
        self.extension = extension if extension is not None else _get_default_ext(self.serializer)
        self.is_binary = False
        makedirs(self.cache_dir, exist_ok=True)

    @contextmanager
    def _try_io(self, ignore_errors: bool = False):
        """Attempt an I/O operation, and either ignore errors or re-raise them as KeyErrors"""
        try:
            yield
        except (IOError, OSError, PickleError) as e:
            if not ignore_errors:
                raise KeyError(e)

    def _path(self, key):
        ext = f'.{self.extension}' if self.extension else ''
        return join(self.cache_dir, f'{key}{ext}')

    def __getitem__(self, key):
        mode = 'rb' if self.is_binary else 'r'
        with self._try_io():
            try:
                with open(self._path(key), mode) as f:
                    return self.serializer.loads(f.read())
            except UnicodeDecodeError:
                self.is_binary = True
                return self.__getitem__(key)

    def __delitem__(self, key):
        with self._try_io():
            unlink(self._path(key))

    def __setitem__(self, key, value):
        serialized_value = self.serializer.dumps(value)
        if isinstance(serialized_value, bytes):
            self.is_binary = True
        mode = 'wb' if self.is_binary else 'w'
        with self._try_io():
            with open(self._path(key), mode) as f:
                f.write(self.serializer.dumps(value))

    def __iter__(self):
        yield from self.keys()

    def __len__(self):
        return len(listdir(self.cache_dir))

    def clear(self):
        with self._try_io(ignore_errors=True):
            rmtree(self.cache_dir, ignore_errors=True)
            makedirs(self.cache_dir)

    def keys(self):
        return [splitext(basename(path))[0] for path in self.paths()]

    def paths(self) -> List[str]:
        """Get absolute file paths to all cached responses"""
        return glob(self._path('*'))


def _get_default_ext(serializer) -> str:
    for k, v in SERIALIZERS.items():
        if serializer is v:
            return k.replace('pickle', 'pkl')
    return ''
