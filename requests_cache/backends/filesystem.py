"""Filesystem cache backend. For usage details, see :ref:`Backends: Filesystem <filesystem>`.

.. automodsumm:: requests_cache.backends.filesystem
   :classes-only:
   :nosignatures:
"""

from contextlib import contextmanager
from logging import getLogger
from os import makedirs
from pathlib import Path
from pickle import PickleError
from shutil import rmtree
from threading import RLock
from typing import Any, Iterator, Optional

from ..serializers import SerializerType, json_serializer
from . import BaseCache, BaseStorage, StrOrPath
from .lru import LRUDict
from .sqlite import SQLiteDict, get_cache_path

DEFAULT_MAX_CACHE_BYTES = 10 * 1024 * 1024  # 10MB
logger = getLogger(__name__)


class FileCache(BaseCache):
    """Filesystem cache backend.

    Args:
        cache_name: Base directory for cache files
        use_cache_dir: Store database in a user cache directory (e.g., `~/.cache/`)
        use_temp: Store cache files in a temp directory (e.g., ``/tmp/http_cache/``).
            Note: if ``cache_name`` is an absolute path, this option will be ignored.
        decode_content: Decode JSON or text response body into a human-readable format
        extension: Extension for cache files. If not specified, the serializer default extension
            will be used.
        maximum_cache_bytes: Maximum total size of all cached responses on the file system in bytes
            If a response is larger than this, it will not be cached.
            If a response would make the cache bigger than this, the oldest response gets dropped.
            By default, the size is not limited.
        block_bytes: The size of a block of data on the file system.
            The file size will be computed as multiples of this.
            Default is 1 byte.
            Only used if ``maximum_cache_bytes`` is set.
        maximum_file_bytes: The maximum size of a single file.
            By default, this is the same as ``maximum_cache_bytes``.
            Only used if ``maximum_cache_bytes`` is set.
        lock: An optional lock to use for the directory.
            By default, this is a :class:`threading.RLock`.
            You can also use :attr:`filelock.FileLock` and a :class:`multiprocessing.RLock`.
    """

    def __init__(
        self,
        cache_name: StrOrPath = 'http_cache',
        use_temp: bool = False,
        decode_content: bool = True,
        serializer: Optional[SerializerType] = None,
        **kwargs,
    ):
        super().__init__(cache_name=str(cache_name), **kwargs)
        skwargs = {'serializer': serializer, **kwargs} if serializer else kwargs
        self.responses: FileDict = (LRUFileDict if 'maximum_cache_bytes' in kwargs else FileDict)(
            cache_name, use_temp=use_temp, decode_content=decode_content, **skwargs
        )
        with self.lock:
            self.redirects: SQLiteDict = SQLiteDict(
                self.cache_dir / 'redirects.sqlite', 'redirects', serializer=None, **kwargs
            )

    @property
    def lock(self) -> RLock:
        """The lock used by the cache."""
        return self.responses.lock

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
        with self.lock:
            self.redirects.init_db()

    def delete(self, *args, **kwargs):
        with self.lock:
            return super().delete(*args, **kwargs)


class FileDict(BaseStorage):
    """A dictionary-like interface to files on the local filesystem.

    The cache directory will be created if it doesn't already exist.
    """

    def __init__(
        self,
        cache_name: StrOrPath,
        use_temp: bool = False,
        use_cache_dir: bool = False,
        extension: Optional[str] = None,
        serializer: Optional[SerializerType] = json_serializer,
        lock: Optional[RLock] = None,
        **kwargs,
    ):
        super().__init__(serializer=serializer, **kwargs)
        self.cache_dir = get_cache_path(cache_name, use_cache_dir=use_cache_dir, use_temp=use_temp)
        self.extension = _get_extension(extension, self.serializer)
        self.is_binary = getattr(self.serializer, 'is_binary', False)
        self._lock = lock if lock is not None else RLock()
        makedirs(self.cache_dir, exist_ok=True)

    @property
    def lock(self) -> RLock:
        """The lock used by the cache."""
        return self._lock

    @contextmanager
    def _try_io(self, key: Optional[str] = None, ignore_errors: bool = False):
        """Attempt an I/O operation, and either ignore errors or re-raise them as KeyErrors"""
        try:
            with self._lock:
                yield
        except (EOFError, IOError, OSError, PickleError) as e:
            if not ignore_errors:
                raise KeyError(f'File for key {key!r} not found.') from e

    def _key2path(self, key: str) -> Path:
        return self.cache_dir / f'{key}{self.extension}'

    def __getitem__(self, key: str):
        mode = 'rb' if self.is_binary else 'r'
        with self._try_io(key):
            with self._key2path(key).open(mode) as f:
                return self.deserialize(key, f.read())

    def __delitem__(self, key):
        with self._try_io(key):
            self._key2path(key).unlink()

    def __setitem__(self, key, value):
        with self._try_io(key):
            with self._key2path(key).open(mode='wb' if self.is_binary else 'w') as f:
                f.write(self.serialize(value))

    def __contains__(self, key) -> bool:
        with self._lock:
            return self._key2path(key).exists()

    def __iter__(self) -> Iterator[str]:
        yield from self.keys()

    def __len__(self) -> int:
        return sum(1 for _ in self.paths())

    def clear(self) -> None:
        """Empty the cache directory."""
        with self._try_io(ignore_errors=True):
            rmtree(self.cache_dir, ignore_errors=True)
            self.cache_dir.mkdir()

    def keys(self):
        return [path.stem for path in self.paths()]

    def paths(self) -> Iterator[Path]:
        """Get absolute file paths to all cached responses"""
        with self._lock:
            return self.cache_dir.glob(f'*{self.extension}')

    def size(self) -> int:
        """Return the size of the database, in bytes"""
        with self._lock:
            return sum(path.stat().st_size for path in self.paths())


class LRUFileDict(FileDict):
    """A size-restricted version of FileDict, using LRU eviction.

    Args:
        block_bytes: The size of a block of data on the file system.
            File sizes will be aligned with this.
        maximum_cache_bytes: The maximum total size of all files in the cache.
        maximum_file_bytes: The maximum size of a single file.
            By default, this is the same as ``maximum_cache_bytes``.
    """

    def __init__(
        self,
        *args,
        block_bytes: int = 1,
        maximum_cache_bytes: int = DEFAULT_MAX_CACHE_BYTES,
        maximum_file_bytes: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.maximum_cache_bytes = maximum_cache_bytes
        self.block_bytes = block_bytes
        self.maximum_file_bytes = maximum_file_bytes or maximum_cache_bytes
        if self.maximum_file_bytes > self.maximum_cache_bytes:
            raise ValueError(
                f'maximum_file_bytes must be smaller or equal to maximum_cache_bytes ({maximum_cache_bytes})'
            )
        if self.block_bytes > self.maximum_file_bytes:
            raise ValueError(
                f'block_bytes must be smaller than maximum_file_bytes ({maximum_file_bytes})'
            )
        if self.block_bytes < 1:
            raise ValueError(f'block_bytes must be greater than 0, not {block_bytes}')

        self.lru_index = LRUDict(self.cache_dir / 'lru.db', 'lru', **kwargs)

    def size(self) -> int:
        """Return the size of the database, in bytes"""
        return self.lru_index.total_size()

    def __getitem__(self, key):
        """Get a value and update its access time in the LRU index"""
        value = super().__getitem__(key)

        # Update access time in LRU index
        try:
            self.lru_index.update_access_time(key)
        # File is missing from LRU index
        except KeyError:
            file_path = self._key2path(key)
            if file_path.exists():
                file_size = self.get_size_on_disk(file_path.stat().st_size)
                self.lru_index[key] = file_size

        return value

    def __setitem__(self, key: str, value: Any) -> None:
        content = self.serialize(value)
        data = content.encode('UTF-8') if isinstance(content, str) else content
        del content
        file_size = self.get_size_on_disk(len(data))

        if file_size > self.maximum_file_bytes:
            logger.debug(
                f'Not caching {key!r} because it is larger than {self.maximum_file_bytes} bytes.'
            )
            return

        with self._try_io(key):
            try:
                super().__delitem__(key)
            except KeyError:
                pass

            # Make space if needed before writing file
            self._evict(file_size)
            super().__setitem__(key, value)

            # Update LRU index with new file size and access time
            self.lru_index[key] = file_size

    def __delitem__(self, key):
        """Delete a file and remove it from the LRU index"""
        # Delete physical file
        super().__delitem__(key)

        # Remove from LRU index
        try:
            del self.lru_index[key]
        except KeyError:
            pass

    def _evict(self, desired_free_bytes: int):
        """Make space in the cache to fit the given number of bytes, if needed.

        This starts deleting the least recently used entries first.
        """
        current_size = self.lru_index.total_size()
        # No eviction needed
        if current_size + desired_free_bytes <= self.maximum_cache_bytes:
            return

        # Get LRU keys to evict based on how much space we need
        space_needed = current_size + desired_free_bytes - self.maximum_cache_bytes
        keys_to_evict = self.lru_index.get_lru(space_needed)

        # Delete the files and LRU entries
        for key in keys_to_evict:
            try:
                del self[key]
            except KeyError:
                pass

    def clear(self):
        """Clear the cache directory and LRU index."""
        super().clear()
        self.lru_index.clear()
        self._lru_initialized = False

    def get_size_on_disk(self, file_size: int) -> int:
        """Return a file size on disk, rounded up to fit the blocks on the file system"""
        sign = -1 if file_size < 0 else 1
        return (
            (file_size * sign + self.block_bytes - 1) // self.block_bytes * self.block_bytes * sign
        )


def _get_extension(extension: Optional[str] = None, serializer=None) -> str:
    """Use either the provided file extension, or get the serializer's default extension"""
    if extension:
        return f'.{extension}'
    subs = {
        'bson': 'bson',
        'safe_pickle': 'pkl',
        'pickle': 'pkl',
        'orjson': 'json',
        'ujson': 'json',
    }
    if serializer and (name := serializer.name):
        for k, v in subs.items():
            name = name.replace(k, v)
        return f'.{name}'
    return '.dat'
