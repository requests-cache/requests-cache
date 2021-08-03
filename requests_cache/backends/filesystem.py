from contextlib import contextmanager
from os import listdir, makedirs, unlink
from os.path import abspath, dirname, expanduser, isabs, join, splitext
from pathlib import Path
from pickle import PickleError
from shutil import rmtree
from tempfile import gettempdir
from typing import Union

from ..serializers import SERIALIZERS
from . import BaseCache, BaseStorage
from .sqlite import DbDict


class FileCache(BaseCache):
    """Backend that stores cached responses as files on the local filesystem.
    Response paths will be in the format ``<cache_name>/responses/<cache_key>``.
    Redirects are stored in a SQLite database, located at ``<cache_name>/redirects.sqlite``.

    Args:
        cache_name: Base directory for cache files
        use_temp: Store cache files in a temp directory (e.g., ``/tmp/http_cache/``).
            Note: if ``cache_name`` is an absolute path, this option will be ignored.
        extension: Extension for cache files. If not specified, the serializer default extension
            will be used.
    """

    def __init__(self, cache_name: Union[Path, str] = 'http_cache', use_temp: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.responses = FileDict(cache_name, use_temp=use_temp, **kwargs)
        db_path = join(dirname(self.responses.cache_dir), 'redirects.sqlite')
        self.redirects = DbDict(db_path, 'redirects', **kwargs)


class FileDict(BaseStorage):
    """A dictionary-like interface to files on the local filesystem"""

    def __init__(self, cache_name, use_temp: bool = False, extension: str = None, **kwargs):
        super().__init__(**kwargs)
        self.cache_dir = _get_cache_dir(cache_name, use_temp)
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
        for filename in listdir(self.cache_dir):
            yield splitext(filename)[0]

    def __len__(self):
        return len(listdir(self.cache_dir))

    def clear(self):
        with self._try_io(ignore_errors=True):
            rmtree(self.cache_dir, ignore_errors=True)
            makedirs(self.cache_dir)

    def paths(self):
        """Get file paths to all cached responses"""
        for key in self:
            yield self._path(key)


def _get_cache_dir(cache_dir: Union[Path, str], use_temp: bool) -> str:
    # Save to a temp directory, if specified
    if use_temp and not isabs(cache_dir):
        cache_dir = join(gettempdir(), cache_dir, 'responses')

    # Expand relative and user paths (~/*), and make sure parent dirs exist
    cache_dir = abspath(expanduser(str(cache_dir)))
    makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _get_default_ext(serializer) -> str:
    for k, v in SERIALIZERS.items():
        if serializer is v:
            return k.replace('pickle', 'pkl')
    return ''
