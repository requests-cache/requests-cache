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
        self.responses: FileDict = (
            LimitedFileDict if 'maximum_cache_bytes' in kwargs else FileDict
        )(cache_name, use_temp=use_temp, decode_content=decode_content, **skwargs)
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


TEN_MB = 10 * 1024 * 1024


class LimitedFileDict(FileDict):
    """A size-restricted version of the file-dict (LRU cache).

    Args:
        maximum_cache_bytes: The maximum total size of all files in the cache.
            This is 10MB by default.
        block_bytes: The size of a block of data on the file system.
            The file size will be computed as multiples of this.
            This is 1 by default.
        maximum_file_bytes: The maximum size of a single file.
            By default, this is the same as ``maximum_cache_bytes``.

    """

    def __init__(
        self,
        *args,
        maximum_cache_bytes: int = TEN_MB,
        block_bytes: int = 1,
        maximum_file_bytes: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.maximum_cache_bytes = maximum_cache_bytes
        self.block_bytes = block_bytes
        self.maximum_file_bytes = (
            maximum_file_bytes if maximum_file_bytes is not None else maximum_cache_bytes
        )
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

        self.lru_index = LRUDict(self.cache_dir / 'lru.db', 'lru', serializer=None, **kwargs)

    # TODO
    # def size(self) -> int:
    #     """Return the size of the database, in bytes"""

    # def _add_to_total_bytes(self, difference_in_bytes: int):
    #     """Change the size of the cache."""
    #     with self._lock:
    #         difference_in_bytes = self.compute_file_size(self.block_bytes, difference_in_bytes)
    #         self.size_file.write_text(str(difference_in_bytes + self.total_bytes))

    # def __delitem__(self, key: str) -> None:
    #     """Delete a value for a key, and update total cache size"""
    #     # TODO

    def __setitem__(self, key: str, value: Any) -> None:
        content = self.serialize(value)
        data = content.encode('UTF-8') if isinstance(content, str) else content
        del content
        if len(data) > self.maximum_file_bytes:
            logger.debug(
                f'Not caching {key!r} because it is larger than {self.maximum_file_bytes} bytes.'
            )
            return

        with self._try_io(key):
            try:
                del self[key]
            except KeyError:
                pass
            self._make_space(len(data))
            # TODO

    def _drop_oldest_key(self) -> bool:
        """Drop the oldest key.

        Returns:
            True if a key was dropped, False if not.
        """
        # TODO

    def _make_space(self, desired_free_bytes: int):
        """Make space in the cache to fit the given number of bytes.

        This starts deleting the oldest entries first.
        If you want more space than available, nothing happens.
        """
        desired_free_bytes = self.compute_file_size(self.block_bytes, desired_free_bytes)
        # TODO

    @staticmethod
    def compute_file_size(block_size: int, file_size: int) -> int:
        """Return the size in bytes of the file, rounded up to fit the blocks on the file system"""
        sign = -1 if file_size < 0 else 1
        return (file_size * sign + block_size - 1) // block_size * block_size * sign


class LRUDict(SQLiteDict):
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
                CREATE TRIGGER cache_insert
                AFTER INSERT ON {self.table_name}
                BEGIN
                    UPDATE {self.table_name}_size
                    SET total_size = total_size + NEW.size;
                END;
                """
            )
            con.execute(
                f"""
                CREATE TRIGGER cache_delete
                AFTER DELETE ON {self.table_name}
                BEGIN
                    UPDATE {self.table_name}_size
                    SET total_size = total_size - OLD.size;
                END;
                """
            )
            con.execute(
                f"""
                CREATE TRIGGER cache_update
                AFTER UPDATE OF size ON {self.table_name}
                WHEN OLD.size != NEW.size
                BEGIN
                    UPDATE {self.table_name}_size
                    SET total_size = total_size + (NEW.size - OLD.size);
                END;
                """
            )

    def __getitem__(self, key):
        with self.connection() as con:
            # Using placeholders here with python 3.12+ and concurrency results in the error:
            # sqlite3.InterfaceError: bad parameter or other API misuse
            row = con.execute(
                f"SELECT access_time FROM {self.table_name} WHERE key='{key}'"
            ).fetchone()
            if not row:
                raise KeyError(key)

            # update access time
            # con.execute(f'UPDATE {self.table_name} SET access_time = ? WHERE key = ?', (int(time.time_ns()), key))
            return row[0]

    # TODO: 'old.access_time' is not valid syntax in SQLite
    # def get_and_update_time(self, key):
    #     timestamp = int(time_ns())
    #     with self.connection(commit=True) as con:
    #         row = con.execute(
    #             f'UPDATE {self.table_name} SET access_time = ? WHERE key = ? '
    #             'RETURNING old.access_time'(timestamp, key),
    #         ).fetchone()
    #         if row is None:
    #             raise KeyError(key)
    #         return row[0]

    def update_access_time(self, key: str):
        """Update the given key with the current timestamp"""
        timestamp = int(time_ns())
        with self.connection() as con:
            con.execute(
                f'UPDATE {self.table_name} SET access_time = ? WHERE key = ?',
                (timestamp, key),
            )

    # def __delitem__(self, key):
    #     """Delete an item and update total cache size"""
    #     with self.connection(commit=True) as con:
    #         row = con.execute(
    #             f'DELETE FROM {self.table_name} WHERE key = ? RETURNING size', (key,)
    #         ).fetchone()

    #         # Update total size
    #         if not row:
    #             raise KeyError

    #         con.execute(
    #             f'UPDATE {self.table_name}_size SET total_size = total_size - ?',
    #             (row[0],),
    #         )

    def __setitem__(self, key: str, size: int):
        """Save a value (file size), and update access time and total cache size"""

        timestamp = int(time_ns())
        with self.connection(commit=True) as con:
            # row = con.execute(
            #     f'SELECT size FROM {self.table_name} WHERE key = ?',
            #     (key,),
            # ).fetchone()
            # old_size = row[0] if row else 0
            # size_diff = size - old_size
            # print(f'Old size for {key!r}: {old_size}, new size: {size}, diff: {size_diff}')
            con.execute(
                f"""
                INSERT INTO {self.table_name} (key, access_time, size)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE
                SET access_time = excluded.access_time, size = excluded.size
                """,
                (key, timestamp, size),
            )

            # # Update total size
            # if size_diff:
            #     con.execute(
            #         f'UPDATE {self.table_name}_size SET total_size = total_size + ?',
            #         (size_diff,),
            #     )

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

    def clear(self):
        super().clear()
        with self.connection(commit=True) as con:
            con.execute(f'UPDATE {self.table_name}_size SET total_size = 0')

    def count(self, *args, **kwargs):
        with self.connection() as con:
            return con.execute(f'SELECT COUNT(key) FROM {self.table_name}').fetchone()[0]

    def sorted(self, *args, **kwargs):
        raise NotImplementedError

    def total_size(self) -> int:
        with self.connection() as con:
            row = con.execute(f'SELECT total_size FROM {self.table_name}_size').fetchone()
            return row[0] if row else 0


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


___all__ = ['FileCache', 'FileDict', 'LimitedFileDict']
