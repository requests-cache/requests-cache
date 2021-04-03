# TODO: Add option for compression?
from contextlib import contextmanager
from os import listdir, makedirs, unlink
from os.path import abspath, expanduser, isabs, join
from pathlib import Path
from pickle import PickleError
from shutil import rmtree
from tempfile import gettempdir
from typing import Union

from . import BaseCache, BaseStorage
from .sqlite import DbDict


class FileCache(BaseCache):
    """Backend that stores cached responses as files on the local filesystem. Response paths will be
    in the format ``<cache_name>/<cache_key>``. Redirects are stored in a SQLite database.

    Args:
        cache_name: Base directory for cache files
        use_temp: Store cache files in a temp directory (e.g., ``/tmp/http_cache/``).
            Note: if ``cache_name`` is an absolute path, this option will be ignored.
    """

    def __init__(self, cache_name: Union[Path, str] = 'http_cache', use_temp: bool = False, **kwargs):
        super().__init__(**kwargs)
        cache_dir = _get_cache_dir(cache_name, use_temp)
        self.responses = FileDict(cache_dir, **kwargs)
        self.redirects = DbDict(join(cache_dir, 'redirects.sqlite'), 'redirects', **kwargs)


class FileDict(BaseStorage):
    """A dictionary-like interface to files on the local filesystem"""

    def __init__(self, cache_dir, **kwargs):
        kwargs.setdefault('suppress_warnings', True)
        super().__init__(**kwargs)
        self.cache_dir = cache_dir
        makedirs(self.cache_dir, exist_ok=True)

    @contextmanager
    def _try_io(self, ignore_errors: bool = False):
        """Attempt an I/O operation, and either ignore errors or re-raise them as KeyErrors"""
        try:
            yield
        except (IOError, OSError, PickleError) as e:
            if not ignore_errors:
                raise KeyError(e)

    def __getitem__(self, key):
        with self._try_io():
            with open(join(self.cache_dir, str(key)), 'rb') as f:
                return self.deserialize(f.read())

    def __delitem__(self, key):
        with self._try_io():
            unlink(join(self.cache_dir, str(key)))

    def __setitem__(self, key, value):
        with self._try_io():
            with open(join(self.cache_dir, str(key)), 'wb') as f:
                f.write(self.serialize(value))

    def __iter__(self):
        for filename in listdir(self.cache_dir):
            yield filename

    def __len__(self):
        return len(listdir(self.cache_dir))

    def clear(self):
        with self._try_io(ignore_errors=True):
            rmtree(self.cache_dir)
            makedirs(self.cache_dir)

    def paths(self):
        """Get file paths to all cached responses"""
        for key in self:
            yield join(self.cache_dir, key)


def _get_cache_dir(cache_dir: Union[Path, str], use_temp: bool) -> str:
    if use_temp and not isabs(cache_dir):
        cache_dir = join(gettempdir(), cache_dir)
    cache_dir = abspath(expanduser(str(cache_dir)))
    makedirs(cache_dir, exist_ok=True)
    return cache_dir
