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
from time import time_ns
from typing import Any, Iterator, Optional

from ..serializers import SerializerType, json_serializer
from . import BaseCache, BaseStorage, StrOrPath
from .sqlite import SQLiteDict, get_cache_path

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
        max_cache_bytes: Enable LRU caching, and set the maximum total size (in bytes) of cached
            responses on the file system.
        max_file_bytes: The maximum size of a single file.
            By default, this is the same as ``max_cache_bytes``.
            Only used if ``max_cache_bytes`` is set.
        block_bytes: The size of a block of data on the file system, which will be used when
            computing total file size on disk. Only used if ``max_cache_bytes`` is set.
        sync_index: On startup, sync LRU metadata with any changes on disk since last use. Use this
            if you intend to modify cache files outside of requests-cache. Leave off to reduce
            startup time for larger caches. Only used if ``max_cache_bytes`` is set.
        lock: Replace the default :class:`threading.RLock` object without your own. Use this if you
            want to share the lock between multiple cache instances, and/or use a different lock
            type (such as :py:class:`multiprocessing.RLock` or :py:class:`filelock.FileLock`).
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
        self.responses: FileDict = (LRUFileDict if 'max_cache_bytes' in kwargs else FileDict)(
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
        max_cache_bytes: The maximum total size of all files in the cache.
        max_file_bytes: The maximum size of a single file.
            By default, this is the same as ``max_cache_bytes``.
        sync_index: Check for filesystem changes since last use. Use this if you intend to modify
            cache files outside of requests-cache. Leave off to reduce startup time for larger caches.
    """

    def __init__(
        self,
        *args,
        block_bytes: int = 1,
        max_cache_bytes: int = 100 * 1024 * 1024,  # 100MB
        max_file_bytes: Optional[int] = None,
        sync_index: bool = False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.max_cache_bytes = max_cache_bytes
        self.block_bytes = block_bytes
        self.max_file_bytes = max_file_bytes or max_cache_bytes
        if self.max_file_bytes > self.max_cache_bytes:
            raise ValueError(
                f'max_file_bytes must be smaller or equal to max_cache_bytes ({max_cache_bytes})'
            )
        if self.block_bytes > self.max_file_bytes:
            raise ValueError(f'block_bytes must be smaller than max_file_bytes ({max_file_bytes})')
        if self.block_bytes < 1:
            raise ValueError(f'block_bytes must be greater than 0, not {block_bytes}')

        self.lru_index = LRUDict(self.cache_dir / 'lru.db', 'lru', **kwargs)
        # Rebuild LRU index if explicitly asked,
        # or for a new cache (potentially with existing files but no metadata)
        if sync_index or len(self.lru_index) == 0:
            self._sync_lru_index()

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
                file_size = self._get_size_on_disk(file_path.stat().st_size)
                self.lru_index[key] = file_size

        return value

    def __setitem__(self, key: str, value: Any) -> None:
        content = self.serialize(value)
        data = content.encode('UTF-8') if isinstance(content, str) else content
        del content
        file_size = self._get_size_on_disk(len(data))

        if file_size > self.max_file_bytes:
            logger.debug(
                f'Not caching {key!r} because it is larger than {self.max_file_bytes} bytes.'
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
        # Remove from LRU index
        try:
            del self.lru_index[key]
        except KeyError:
            pass

        super().__delitem__(key)

    def _evict(self, desired_free_bytes: int):
        """Make space in the cache to fit the given number of bytes, if needed.

        This starts deleting the least recently used entries first.
        """
        current_size = self.lru_index.total_size()
        space_needed = current_size + desired_free_bytes - self.max_cache_bytes
        if space_needed <= 0:
            return

        # Get LRU keys to evict based on how much space we need
        keys_to_evict = self.lru_index.get_lru(space_needed)
        for key in keys_to_evict:
            try:
                del self[key]
            except KeyError:
                pass

    def _sync_lru_index(self):
        """Rebuild the LRU index from files on disk"""
        with self._lock:
            self.lru_index.clear()
            for path in self.paths():
                key = path.stem
                self.lru_index[key] = self._get_size_on_disk(path.stat().st_size)

    def _get_size_on_disk(self, file_size: int) -> int:
        """Return a file size on disk, rounded up to fit the blocks on the file system"""
        sign = -1 if file_size < 0 else 1
        return (
            (file_size * sign + self.block_bytes - 1) // self.block_bytes * self.block_bytes * sign
        )

    def clear(self):
        """Clear the cache directory and LRU index."""
        super().clear()
        self.lru_index.clear()
        self._lru_initialized = False

    def size(self) -> int:
        """Return the size of the database, in bytes"""
        return self.lru_index.total_size()


class LRUDict(SQLiteDict):
    """A SQLite db used to track LRU metadata for cached items:

    * ``key``: The cache key
    * ``access_time``: The last access time, as a UNIX timestamp in nanoseconds
    * ``size``: The size of the cached item, in bytes
    * ``total_size`` Combined size of all cache items in bytes, accessed with :py:meth:`total_size`.

    Implementation Notes:

    * ``total_size`` is managed by triggers and stored in a separate single-row table.
    * As a dict-like interface, ``size`` is treated as the main value and ``access_time`` is set
      automatically and updated with :py:meth:`update_access_time`.
    * :py:meth:`get_lru` Can select multiple keys to evict, up to an arbitrary total size, within a
      single query using a window function.
    """

    def __init__(self, *args, **kwargs):
        kwargs.pop('serializer', None)
        super().__init__(*args, **kwargs)

    def init_db(self):
        self.close()
        with self.connection(commit=True) as con:
            # Table for LRU metadata
            con.execute(
                f'CREATE TABLE IF NOT EXISTS {self.table_name} ('
                '    key TEXT PRIMARY KEY,'
                '    access_time INTEGER NOT NULL,'
                '    size INTEGER NOT NULL'
                ')'
            )
            con.execute(
                f'CREATE INDEX IF NOT EXISTS idx_access_time ON {self.table_name}(access_time)'
            )
            con.execute(f'CREATE INDEX IF NOT EXISTS idx_size ON {self.table_name}(size)')

            # Single-row table to persist total cache size
            con.execute(
                f'CREATE TABLE IF NOT EXISTS {self.table_name}_size ('
                '    total_size INTEGER NOT NULL'
                ')'
            )
            con.execute(f'INSERT OR IGNORE INTO {self.table_name}_size (total_size) VALUES (0)')

            # Triggers to update total size
            con.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {self.table_name}_insert
                AFTER INSERT ON {self.table_name}
                BEGIN
                    UPDATE {self.table_name}_size
                    SET total_size = total_size + NEW.size;
                END;
                """
            )
            con.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {self.table_name}_delete
                AFTER DELETE ON {self.table_name}
                BEGIN
                    UPDATE {self.table_name}_size
                    SET total_size = total_size - OLD.size;
                END;
                """
            )
            con.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS {self.table_name}_update
                AFTER UPDATE OF size ON {self.table_name}
                WHEN OLD.size != NEW.size
                BEGIN
                    UPDATE {self.table_name}_size
                    SET total_size = total_size + (NEW.size - OLD.size);
                END;
                """
            )

    def __delitem__(self, key):
        with self.connection(commit=True) as con:
            cur = con.execute(f'DELETE FROM {self.table_name} WHERE key=?', (key,))
        if not cur.rowcount:
            raise KeyError

    def __getitem__(self, key) -> int:
        with self.connection() as con:
            # Using placeholders here with python 3.12+ and concurrency results in the error:
            # sqlite3.InterfaceError: bad parameter or other API misuse
            row = con.execute(f"SELECT size FROM {self.table_name} WHERE key='{key}'").fetchone()
            if not row:
                raise KeyError(key)
            return row[0]

    def __setitem__(self, key: str, size: int):
        """Save a value (file size), and update access time and total cache size"""

        timestamp = int(time_ns())
        with self.connection(commit=True) as con:
            con.execute(
                f"""
                INSERT INTO {self.table_name} (key, access_time, size)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE
                SET access_time = excluded.access_time, size = excluded.size
                """,
                (key, timestamp, size),
            )

    def clear(self):
        super().clear()
        with self.connection(commit=True) as con:
            con.execute(f'UPDATE {self.table_name}_size SET total_size = 0')

    def count(self, *args, **kwargs):
        with self.connection() as con:
            return con.execute(f'SELECT COUNT(key) FROM {self.table_name}').fetchone()[0]

    def get_lru(self, total_size: int):
        """Get the least recently used keys with a combined size >= total_size"""

        with self.connection() as con:
            cur = con.execute(
                f"""
                WITH ordered AS (
                    SELECT key, size, access_time, SUM(size) OVER (ORDER BY access_time) AS running_total
                    FROM {self.table_name}
                )
                SELECT * FROM ordered WHERE running_total - size < ?
                ORDER BY access_time;
                """,
                (total_size,),
            )
            rows = cur.fetchall()
            cur.close()
            return [row[0] for row in rows]

    def sorted(  # type: ignore
        self,
        key: str = 'access_time',
        reversed: bool = False,
        limit: Optional[int] = None,
        **kwargs,
    ) -> Iterator[str]:
        """Get LRU entries in sorted order, by either ``access_time`` or ``size``"""
        # Get sort key, direction, and limit
        if key not in ['access_time', 'size', 'key']:
            raise ValueError(f'Invalid sort key: {key}')
        direction = 'DESC' if reversed else 'ASC'
        limit_expr = f'LIMIT {limit}' if limit else ''

        with self.connection() as con:
            for row in con.execute(
                f'SELECT key FROM {self.table_name} ORDER BY {key} {direction} {limit_expr}',
            ):
                yield row[0]

    def total_size(self) -> int:
        with self.connection() as con:
            row = con.execute(f'SELECT total_size FROM {self.table_name}_size').fetchone()
            return row[0] if row else 0

    def update_access_time(self, key: str):
        """Update the given key with the current timestamp

        Raises:
            KeyError: If the key doesn't exist in the LRU index
        """
        timestamp = int(time_ns())
        with self.connection(commit=True) as con:
            cur = con.execute(
                f'UPDATE {self.table_name} SET access_time = ? WHERE key = ?',
                (timestamp, key),
            )
        if not cur.rowcount:
            raise KeyError(key)


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
